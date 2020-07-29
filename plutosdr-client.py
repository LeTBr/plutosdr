#!/usr/bin/env python
# coding=utf-8

import math
import socket
import struct
import sys
import traceback

import matplotlib.pyplot as plot
import numpy as np


def main():

    host = ''
    port = 9527

    server_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.bind((host, port))

    if len(sys.argv) != 2:
        remote_addr, remote_port = '127.0.0.1', '5025'
    else:
        remote_addr, remote_port = sys.argv[1].split(':')

    tcp_proxy = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tcp_proxy.connect((remote_addr, int(remote_port)))
    host, _ = tcp_proxy.getsockname()
    tcp_proxy.sendall('*udp={0}:{1}\n'.format(host, port).encode('ascii'))
    tcp_proxy.sendall('*task=on\n'.encode('ascii'))
    tcp_proxy.sendall('#str:tx_enabled:true\n'.encode('ascii'))

    g_frequency = 70000000

    while True:
        try:
            g_frequency %= 6000000000
            message, _ = server_sock.recvfrom(64 * 1024)  # 64k, maximum
            if message[0] == (b'#')[0]:
                identifier, frequency, bandwidth, sampling_rate, attenuation, length = struct.unpack(
                    '=sqqqii', message[:33])
                raw = message[33:]
                raw = struct.unpack('={0}h'.format(length * 2), raw)
                sys.stdout.write('{0}freq={1},bw={2},sr={3},att={4},raw_len={5},raw_sample={6}\n'.format(
                    identifier, frequency, bandwidth, sampling_rate, attenuation, length, raw[:10]))
                tcp_proxy.sendall('#long:tx_frequency:{0}\n'.format(g_frequency+9000000).encode('ascii'))
                tcp_proxy.sendall('#long:frequency:{0}\n'.format(g_frequency).encode('ascii'))
                g_frequency += 1000000
                # Get time domain data (I/Q tuple list), plus, every I/Q data is signed short type
                iq_tuple_list = [(raw[2*i], raw[2*i+1]) for i in range(length)]

                # Get frequency domain data (spectrum)
                spectrum = np.fft.fft([complex(int(iq[0]), int(iq[1])) for iq in iq_tuple_list])
                spectrum = np.fft.fftshift(spectrum)

                # Plot scattered constellation diagram
                # i_data, q_data = zip(*iq_tuple_list)
                # plot.scatter(i_data, q_data)
                # plot.show()

                # Plot spectrum diagram
                # # plot.plot(np.arange(0, 2 * np.pi,  2 * np.pi/len(spectrum)), [math.fabs(spectrum[i]) for i in range(len(spectrum))])
                plot.plot(np.arange(0, 2 * np.pi, 2 * np.pi/len(spectrum)), [20 * (math.log10(abs(i)) - math.log10(len(spectrum))) for i in spectrum])
                plot.show()
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            traceback.print_exc()
    tcp_proxy.shutdown(2)
    tcp_proxy.close()


if __name__ == '__main__':
    main()

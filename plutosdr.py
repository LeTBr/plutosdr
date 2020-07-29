#!/usr/bin/env python3
# -*-coding:utf-8-*-
# Description: This is PlutoSDR service which supplies I/Q through socket

import os
import platform
import socket
import struct
import sys
import threading
import time
import traceback
from ctypes import CDLL as _cdll
from ctypes import WinDLL as _windll
from ctypes import c_int, c_ulong

import iio


def load_libad9361():
    '''
    Load libad9361 library
    '''

    arch, name = platform.architecture()
    if name.lower().startswith('win'):
        path = os.path.join(os.path.dirname(__file__), r'win\x86\libad9361.dll' if arch.lower() == '32bit' else r'win\x64\libad9361.dll')
        return _windll(path)
    path = '/usr/lib/libad9361.so.0'
    if os.path.exists(path):
        return _cdll(path)
    return _cdll('/usr/local/lib/libad9361.so.0')


# Initialize libad9361 module
_lib = load_libad9361()

# Prerequisites for 'ad9316_set_bb_rate' which is used for sampling_frequency setting
_ad9361_set_bb_rate = _lib.ad9361_set_bb_rate
_ad9361_set_bb_rate.argtypes = (iio._DevicePtr, c_ulong)
_ad9361_set_bb_rate.restype = c_int

MAX_IQ_SIZE = 32768


class DeviceService():
    '''
    Adalm-Pluto based on AD9361 manufactured by ADI
    '''

    def __init__(self, sampling_count=2048, context='ip:192.168.2.1'):
        '''
        Initialization
        Paramters:
            handler: when I/Q data get ready, there requires a callback to send data
            sampling_count: I/Q sampling count, default value: 2048,
            context: device context, there requires ip address,
        '''

        sys.stdout.write('Initialize Adalm-Pluto (based on AD936x) ...\n')

        self.__parameters = {
            'frequency': (0, [101700000, (70000000, 1, 6000000000)]),  # RX frequency
            'rf_bandwidth': (4, [2000000, (200000, 1, 56000000)]),   # RX bandwidth
            # 'sampling_frequency': (4, [2500000, (2083333, 1, 61440000)]),
            'sampling_frequency': (4, [2500000, (521000, 1, 61440000)]),  # Sampling Rate
            'gain_control_mode': (4, ['manual', ('manual,fast_attack,slow_attack,hybrid')]),  # Gain control
            'hardwaregain': (4, [-3, (-3, 1, 71)]),  # MGC
            'tx_enabled': (1, ['false', ('true,false')]),  # TX RF out
            'tx_frequency': (1, [101700000, (70000000, 1, 6000000000)]),  # TX frequency
            'tx_hardwaregain': (5, [0, (-89, 1, 0)])  # TX MGC
        }
        self.__callback = None
        self.__capture = None
        self.__start_sampling = False
        self.__lock = threading.Lock()
        self.__abort_sampling_event = threading.Event()
        self.__abort_sampling_event.clear()

        try:
            # Create device context
            retry = 10
            while retry:
                try:
                    self.__ctx = iio.Context(context)
                    break
                except:
                    time.sleep(2)
                    retry -= 1
                    continue

            sys.stdout.write(('Initialize device context.\n'))

            # Initialize device control
            # channel 0, 4 are manipulated by rx
            # channel 1, 5 are manipulated by tx
            self.__ctrl = self.__ctx.find_device('ad9361-phy')

            # Initialize RX/TX ctrl parameters
            self.__ctrl.channels[0].attrs['powerdown'].value = '1'
            self.__ctrl.channels[0].attrs['frequency'].value = '101700000'
            self.__ctrl.channels[4].attrs['rf_bandwidth'].value = '2000000'
            self.__ctrl.channels[4].attrs['gain_control_mode'].value = 'slow_attack'
            self.__ctrl.channels[4].attrs['rf_port_select'].value = 'A_BALANCED'
            self.__ctrl.channels[1].attrs['powerdown'].value = '1'
            self.__ctrl.channels[1].attrs['frequency'].value = '101700000'
            self.__ctrl.channels[5].attrs['rf_bandwidth'].value = '2000000'
            self.__ctrl.channels[5].attrs['hardwaregain'].value = '0'
            _ad9361_set_bb_rate(self.__ctrl._device, 2560000)
            sys.stdout.write('Initialize CTRL: \"ad9361-phy\".\n')

            # Initialize device receiving channels and enable I/Q data output channels
            self.__rx = self.__ctx.find_device('cf-ad9361-lpc')
            sys.stdout.write('Initialize RX: \"cf-ad9361-lpc\".\n')
            self.__rx.channels[0].enabled = True   # I data channel
            self.__rx.channels[1].enabled = True   # Q data channel
            sys.stdout.write('Enable RX I/Q channels.\n')

            # Initialize buffer
            self.__buffer = iio.Buffer(self.__rx, sampling_count, False)
            sys.stdout.write('Initialize I/Q data buffers (sampling count={0}).\n'.format(sampling_count))
        except:
            traceback.print_exc()

    def start(self):
        '''
        Start data sampling
        '''
        sys.stdout.write('Starting device service...\n')
        if self.__capture is None:
            self.__capture = threading.Thread(target=self.__capture_data)
            self.__capture.setDaemon(True)
            self.__capture.start()
            sys.stdout.write('Set new sampling thread.\n')
        self.__lock.acquire()
        self.__start_sampling = True
        self.__lock.release()
        sys.stdout.write('Device service started.\n')

    def stop(self):
        '''
        Stop data sampling
        '''
        sys.stdout.write('Stopping device service...\n')
        self.__lock.acquire()
        self.__start_sampling = False
        self.__lock.release()
        sys.stdout.write('Device service stopped.\n')

    def release(self):
        '''
        Release resources(threads) attached to this object
        '''
        try:
            self.__abort_sampling_event.set()
            if self.__capture:
                self.__capture.join()
                self.__capture = None
                sys.stdout.write('Sampling thread terminated.\n')
            del self.__ctx  # Delete the device context
            sys.stdout.write('Device context deleted.\n')
        except:
            traceback.print_exc()

    def set_parameter(self, name, value):
        '''
        Modify paramter whether the task is running or not
        Parameters:
            name: name of parameter
            value: value of paramter
        '''
        if name not in self.__parameters:
            return
        try:
            self.__lock.acquire()
            if value == self.__parameters[name][1][0]:
                return

            if isinstance(value, (int, )):
                chn_idx, result, (start, _, stop) = self.__parameters[name][0], self.__parameters[name][1][0], self.__parameters[name][1][1]
                if value < start:
                    result = start
                elif value > stop:
                    result = stop
                else:
                    result = value
            elif isinstance(value, str):
                chn_idx, result, enumerates = self.__parameters[name][0], self.__parameters[name][1][0], self.__parameters[name][1][1]
                if value in enumerates.split(','):
                    result = value
                else:
                    return
            else:
                return
            self.__parameters[name][1][0] = result

            if chn_idx == 1 or chn_idx == 5:  # TX channel parameters:
                if name == 'tx_enabled':
                    self.__ctrl.channels[0].attrs['powerdown'].value = '1' if str(result) == 'true' else '0'
                    self.__ctrl.channels[chn_idx].attrs['powerdown'].value = '0' if str(result) == 'true' else '1'
                elif name == 'tx_frequency':
                    self.__ctrl.channels[chn_idx].attrs['frequency'].value = str(result)
                elif name == 'tx_hardwaregain':
                    self.__ctrl.channels[chn_idx].attrs['hardwaregain'].value = str(result)
            else:  # RX channel parameters
                if name == 'sampling_frequency':
                    _ad9361_set_bb_rate(self.__ctrl._device, c_ulong(result))
                else:
                    self.__ctrl.channels[chn_idx].attrs[name].value = str(result)
                    if name == 'rf_bandwidth':
                        self.__ctrl.channels[chn_idx+1].attrs[name].value = str(result)
                        sampling_frequency = int(result * 1.28) if result >= 500000 else 521000
                        # # when rf_bandwidth is set to 1MHz or 5MHz, sampling_frequency will be set to 13.5MHz
                        # if result in (1000000L, 5000000L):
                        #     sampling_frequency = 13500000L
                        _ad9361_set_bb_rate(self.__ctrl._device, c_ulong(sampling_frequency))
                        self.__parameters['sampling_frequency'][1][0] = sampling_frequency
            sys.stdout.write('Set device parameter: \"{0}\" to {1} on channel: {2}\n'.format(name, result, chn_idx))
        except:
            traceback.print_exc()
        finally:
            self.__lock.release()

    def set_data_sinker(self, callback):
        '''
        Set data sinker
        '''
        self.__callback = callback
        sys.stdout.write('Set data callback handler <{0}>\n'.format(id(callback)))

    def __capture_data(self):
        '''
        Sample data thread
        '''
        sys.stdout.write('Sampling thread has get ready.\n')
        while not self.__abort_sampling_event.is_set():
            # Fill the buffer and read data from it.
            # Remark: a while/for loop can be used to gain data continuously
            try:
                self.__lock.acquire()
                if self.__start_sampling:
                    self.__buffer.refill()
                    iq = self.__buffer.read()
                    frequency, bandwidth, sampling_rate, attenuation = self.__parameters['frequency'][1][0], \
                        self.__parameters['rf_bandwidth'][1][0], \
                        self.__parameters['sampling_frequency'][1][0], \
                        self.__ctrl.channels[4].attrs['hardwaregain'].value.split()[0]
                else:
                    # if this sentence is uncomment, a new task setting will be delayed which constraints parameter setting. why?
                    self.__buffer.read()
                    # time.sleep(2)
                    continue
            except (KeyboardInterrupt, SystemExit):
                raise
            except:
                traceback.print_exc()
                continue
            finally:
                self.__lock.release()
            total = len(iq)
            index = 0
            current = 0
            next_ = 0
            while total > MAX_IQ_SIZE:
                current = index * MAX_IQ_SIZE
                next_ = (index+1) * MAX_IQ_SIZE
                partial_iq = iq[current: next_]
                data = struct.pack('=sqqqii', b'#', frequency, bandwidth, sampling_rate, int(float(attenuation)), len(partial_iq)//4)
                data += partial_iq
                if self.__callback:
                    self.__callback(data)
                else:
                    time.sleep(2)
                total -= MAX_IQ_SIZE
                index += 1
            partial_iq = iq[next_:]
            data = struct.pack('=sqqqii', b'#', frequency, bandwidth, sampling_rate, int(float(attenuation)), len(partial_iq)//4)
            data += partial_iq
            if self.__callback:
                self.__callback(data)
            else:
                time.sleep(2)


class NetworkService():
    '''
    Use this network service to dispatch data from device context
    '''

    def __init__(self, device):
        '''
        Construct a network service attached a device
        '''
        sys.stdout.write('Initialize network dispatch service...\n')
        self.__lock = threading.Lock()
        self.__data_sockets = {}
        self.__device = device
        self.__device.set_data_sinker(self.__broadcast_data)
        self.__server_socket = None

    def start(self, host='', port=5025):
        '''
        Start network service
        '''
        sys.stdout.write('Start running network service...\n')
        self.__server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.__server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, True)
        self.__server_socket.bind((host, port))
        self.__server_socket.listen(1)
        sys.stdout.write('Listening on 0.0.0.0:{0}\n'.format(port))
        while True:
            try:
                client_socket, client_addr = self.__server_socket.accept()
                sys.stdout.write('Accept connection from \"{0}:{1}\"\n'.format(client_addr[0], client_addr[1]))
                try:
                    self.__lock.acquire()
                    if len(self.__data_sockets) == 3:
                        sys.stdout.write('Too many connections, this connection <{0}> will be closed forcedly\n'.format(id(client_socket)))
                        client_socket.sendall('Your request has been closed since too many connections.\n')
                        client_socket.shutdown(2)
                        client_socket.close()
                    else:
                        processor = threading.Thread(target=self.__process_client, args=[client_socket])
                        processor.setDaemon(True)
                        processor.start()
                except:
                    raise
                finally:
                    self.__lock.release()
            except KeyboardInterrupt:
                raise
            except:
                traceback.print_exc()
        self.__server_socket.close()

    def stop(self):
        '''
        Stop network service
        '''
        self.__lock.acquire()
        for key in self.__data_sockets:
            try:
                self.__data_sockets[key].shutdown(2)
                self.__data_sockets[key].close()
                self.__data_sockets[key] = None
                sys.stdout.write('client socket<{0}> closed.\n'.format(key))
            except:
                traceback.print_exc()
        self.__data_sockets.clear()
        self.__lock.release()
        self.__device.release()

    def __process_client(self, client_socket):
        '''
        Process command and other input from client socket
        '''
        self.__lock.acquire()
        self.__data_sockets[id(client_socket)] = None
        self.__lock.release()
        fd = client_socket.makefile('rwb', 0)  # convert
        while True:
            try:
                request = fd.readline().lower().decode('ascii').strip()
                sys.stdout.write('Receive request: \"{0}\"\n'.format(request))
                # a star ahead means a command used to initialize networking or task
                if request.startswith('*'):
                    self.__process_task_request(client_socket, request)
                # a sharp ahead means a cluster of parameters used to configure device
                elif request.startswith('#'):
                    self.__process_parameter_request(request)
                # when the fd is unavailable (the current connection has been closed by remote host),
                # the fd.readline method will return empty string in Linux,
                # while in Windows, fd.readline will raise an i/o exception
                elif not request:
                    break
            except:
                traceback.print_exc()
                break
        self.__remove_data_transmission(client_socket)
        fd.close()
        client_socket.close()

    def __process_task_request(self, client_socket, request):
        '''
        Process request concerning networking
        eg. "*udp=192.168.120.1:9527\n", "*task=on\n", "*task=off\n'
        '''
        if not request.startswith('*'):
            return

        requests = request[1:].split(';')
        for req in requests:
            parameter = req.split('=')
            if len(parameter) != 2:
                continue
            name, value = parameter
            if name == 'udp':
                try:
                    self.__lock.acquire()
                    key = id(client_socket)
                    if key in self.__data_sockets and self.__data_sockets[key]:
                        self.__data_sockets[key].close()
                    host, port = value.split(':')
                    data_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    data_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, True)
                    data_socket.connect((host, int(port)))
                    self.__data_sockets[key] = data_socket
                except:
                    traceback.print_exc()
                finally:
                    self.__lock.release()
            elif name == 'task':
                if value == 'on':
                    self.__device.start()
                elif value == 'off':
                    self.__device.stop()

    def __process_parameter_request(self, request):
        '''
        Process parameter setting request
        eg. "#long:frequency:101700000;long:rf_bandwidth:2000000;long:samping_frequency:2500000\n"
        '''
        if not request.startswith('#'):
            return

        requests = request[1:].split(';')
        for req in requests:
            parameter = req.split(':')
            if len(parameter) != 3:
                continue
            param_type, name, value = parameter
            if param_type == 'int' or param_type == 'long':
                value = int(value)
            self.__device.set_parameter(name, value)

    def __broadcast_data(self, data):
        '''
        Broadcast data to all its clients
        '''
        try:
            self.__lock.acquire()
            for key in self.__data_sockets:
                try:
                    if self.__data_sockets[key]:
                        self.__data_sockets[key].sendall(data)
                except:
                    self.__data_sockets[key].close()
                    self.__data_sockets[key] = None
                    traceback.print_exc()
        finally:
            self.__lock.release()

    def __remove_data_transmission(self, client_sock):
        '''
        Close data transmission socket
        '''
        sys.stdout.write('Close data transmission socket: <{0}>\n'.format(id(client_sock)))
        self.__lock.acquire()
        key = id(client_sock)
        if key in self.__data_sockets:
            del self.__data_sockets[key]
        self.__lock.release()


def main():
    try:
        value = int(sys.argv[1])
        if value < 128:
            value = 128
        elif value > 8192:
            value = 8192
    except:
        value = 2048

    network_service = None
    try:
        device_service = DeviceService(sampling_count=value)
        network_service = NetworkService(device_service)
        network_service.start()
    except:
        traceback.print_exc()
    finally:
        if network_service:
            network_service.stop()


if __name__ == '__main__':
    main()

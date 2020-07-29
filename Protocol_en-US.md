# PlutoSDR

## Control Over LAN

- Instructions are sent to server through TCP connection, and data is retrieved from server through UDP whose binding information is told to server through TCP instructions as below.
- Server is listening on TCP port 5025
- Client sends instruction to sever to initialize data retrieving channel. e.g. "*upd=xxx.xxx.xxx.xxx:yyyy\n". it goes to according to IPv4 format in which "xxx.xxx.xxx.xxx"  stands for IP address and "yyyy"  for UDP server port binded on client side.

## Parameters

- Instruction starts with "#" for each parameter like "#long:frequency:101700000\n" or for parameters seperated by ";" like "#long:frequency:101700000;long:rf_bandwidth:2000000;long:samping_frequency:2500000;str:gain_control_mode:slow_attack\n"
- Parameters and their value ranges

    Friendly Name|Name|Type|Value Range
    :--:|--|--|--
    __Center Frequency (RX)__|frequency|long|70MHz~6GHz
    __Bandwidth__|rf_bandwidth|long|200kHz~56MHz
    __Sampling Rate__|samping_frequency|long|2500kHz~64MHz
    __Gain Control__|gain_control_mode|str|[_slow_attack,fast_attack,manual_]
    __MGC__|hardwaregain|int|-3dB~70dB
    __Center Frequency (TX)__|tx_frequency|long|70MHz~6GHz
    __TX Enabled__|tx_enabled|str|[_false,true_]

## Data Format

- Data retrieving from server starts with "#" which is followed by parameter description and I/Q binary sequence
- "#<8 bit for frequency><8 bit for bandwidth><8 bit for sampling rate><4 bit for gain><4 bit for I/Q ___byte count___><___count___ I/Q binary byte sequence>
- Each I or Q data is reprented by 16bit integer, so as mentioned above, I/Q pair count is equal to the value ___byte count___ divides 4

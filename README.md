# PlutoSDR

## Install IIO Python Binding for Linux (Debian distro)

```shell
sudo apt-get install libxml2 libxml2-dev bison flex libcdk5-dev cmake
sudo apt-get install libaio-dev libusb-1.0-0-dev libserialport-dev libxml2-dev libavahi-client-dev doxygen graphviz
sudo cp linux/prerequisites/iiod-usb.conf /etc/init/
sudo cp linux/prerequisites/53-adi-plutosdr-usb.rules /etc/udev/rules.d/
git clone https://github.com/analogdevicesinc/libad9361-iio.git
cd libad9361-iio
cmake .
make all
sudo make install
PATH=/usr/lib/:$PATH
git clone https://github.com/analogdevicesinc/libiio.git
cd libiio/bindings/python
cmake .
sudo python setup.py install
```

## Install IIO for Windows ( cmake is required to be installed in advance)

```text
Go to "win/prerequisites", and install "libiio-0.15-setup.exe"
Go back to the previous directory
run command 'git clone https://github.com/analogdevicesinc/libiio.git'
run command 'cd libiio/bindings/python'
run command 'cmake .'
run command 'py -2 setup.py install' for python2 or 'py -3 setup.py install' for python3 if py is not install, or just 'python setup.py install' for python
```

## See also

- [__lib9361-iio__](https://github.com/analogdevicesinc/libad9361-iio)
- [__libiio__](https://github.com/analogdevicesinc/libiio)

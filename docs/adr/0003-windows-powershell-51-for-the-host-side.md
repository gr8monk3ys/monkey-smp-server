# The host side is Windows PowerShell 5.1, plain ASCII, Windows only

Everything a host runs is double-click `.bat` files calling a Windows PowerShell 5.1 script, because 5.1 ships with every Windows 10 and 11 install and hosts are not expected to install Python, PowerShell 7, Docker or Java themselves. The scripts must stay pure ASCII because 5.1 reads files without a byte-order mark using the system's legacy code page, which corrupts any other character. Maintainer tools are free to use Python, since only maintainers run them. Linux and macOS hosts are out of scope until someone needs them.

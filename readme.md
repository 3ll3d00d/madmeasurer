## Overview

A simple script which uses libbluray in order to work which is the main title for a particular bluray.

## Dependencies

### Linux 

Expects libbluray-dev to be installed

### Windows

You have to build PyBluread yourself, see https://github.com/3ll3d00d/PyBluRead

## Exe

to create an exe

    pyinstaller --clean --log-level=WARN -F for_exe.spec
    
produces 

    dist/madmeasurer.exe

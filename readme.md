## Overview

A simple script which uses libbluray in order to work which is the main title for a particular bluray.

## Dependencies

### PyBluread 

You have to build PyBluread yourself, see https://github.com/3ll3d00d/PyBluRead

### Patching libbluray 

#### on Windows

* clone the repo from videolan - https://code.videolan.org/videolan/libbluray/
* clone the SMH repo - https://github.com/3ll3d00d/libbluray
* copy the SMP dir from here to the videolan repo
* open the libbluray_deps solution in VS 2017
* retarget the solution at Win10
* apply patch/navigation.c.patch 
* build the ReleaseDLLStaticDeps build target
* move the dll from $(ProjectDir)..\..\..\msvc\bin\x64 to deps
* add libfreetype-6.dll and libxml2-2.dll to deps (can be grabbed from jriver plugins dir)

#### on Linux

* TBD  

## Exe

to create an exe

    pyinstaller --clean --log-level=WARN -F for_exe.spec
    
produces 

    dist/madmeasurer.exe
    
## Usage
    
    madmeasurer.exe -h
    usage: madmeasurer.exe [-h] [-v] [-f] [-c] [-m] [-d DEPTH] [-i]
                           [--min-duration MIN_DURATION] [-s] [--use-lav]
                           paths [paths ...]
    
    madmeasurer for BDMV
    
    positional arguments:
      paths                 Path to search (for index.bdmv files)
    
    optional arguments:
      -h, --help            show this help message and exit
      -v, --verbose         Output additional logging, can be added multiple
                            times, use -vvv to see additional debug logging from
                            libbluray
      -f, --force           if a playlist measurement file already exists,
                            overwrite it from index.bdmv anyway
      -c, --copy            Copies index.bdmv.measurements to the specified main
                            title location
      -m, --measure         Calls madMeasureHDR.exe if no measurement file exists
                            and the main title is a UHD
      -d DEPTH, --depth DEPTH
                            Maximum folder search depth, if unset will append /**
                            to every search path
      -i, --iso             Search for ISO files instead of index.bdmv
      --min-duration MIN_DURATION
                            Minimum playlist duration in minimums to be considered
                            a main title
      -s, --silent          Print the main title name only (NB: only make sense
                            when searching for one title)
      --use-lav             Finds the main title using the same algorithm as
                            LAVSplitter (longest duration)


## Running Locally

* add deps to PYTHONPATH and PATH?

## Debugging libbluray

set environment variables as follows

    set BD_DEBUG_FILE=/some/file.log
    set BD_DEBUG_MASK=0x00100
    
debug mask values are shown in https://code.videolan.org/videolan/libbluray/blob/master/src/util/log_control.h#L31


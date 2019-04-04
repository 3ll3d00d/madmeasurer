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
    usage: madmeasurer.exe [-h] [-d DEPTH] [-i] [-e [EXTENSION [EXTENSION ...]]]
                           [--min-duration MIN_DURATION] [--use-lav] [--include-hd]
                           [-f] [-c] [-m] [--mad-measure-path MAD_MEASURE_PATH]
                           [--measure-all-playlists] [-v] [-s] [--dry-run]
                           [--bd-debug-mask BD_DEBUG_MASK]
                           paths [paths ...]
    
    madmeasurer for BDMV
    
    positional arguments:
      paths                 Search paths
    
    optional arguments:
      -h, --help            show this help message and exit
    
    Search:
      -d DEPTH, --depth DEPTH
                            Maximum folder search depth If unset will append /**
                            to every search path unless an explicit complete path
                            to an iso or index.bdmv is provided (in which case it
                            is ignored)
      -i, --iso             Search for ISO files instead of index.bdmv
      -e [EXTENSION [EXTENSION ...]], --extension [EXTENSION [EXTENSION ...]]
                            Search for files with the specified extension(s)
      --min-duration MIN_DURATION
                            Minimum playlist duration in minutes to be considered
                            a main title or measurement candidate
      --use-lav             Finds the main title using the same algorithm as
                            LAVSplitter (longest duration)
      --include-hd          Extend search to cover non UHD BDs
    
    Measure:
      -f, --force           if a playlist measurement file already exists,
                            overwrite it from index.bdmv anyway
      -c, --copy            Copies index.bdmv.measurements to the specified main
                            title location
      -m, --measure         Calls madMeasureHDR.exe if no measurement file exists
                            and the main title is a UHD
      --mad-measure-path MAD_MEASURE_PATH
                            Path to madMeasureHDR.exe (can set via
                            MAD_MEASURE_HDR_PATH env var)
      --measure-all-playlists
                            Use with -m to also measure playlists longer than min-
                            duration
    
    Output:
      -v, --verbose         Output additional logging Can be added multiple times
                            Use -vvv to see additional debug logging from
                            libbluray
      -s, --silent          Print the main title name only (NB: only make sense
                            when searching for one title)
      --dry-run             Execute without changing any files
      --bd-debug-mask BD_DEBUG_MASK
                            Specifies a debug mask to be passed as BD_DEBUG_MASK
                            for libbluray

## Examples

### Get the main playlist for a single title

To get the playlist name only

    $ madmeasurer.exe -s "w:/A Quiet Place/BDMV/index.bdmv"
    00800.mpls
    
To get the full playlist path

    $ madmeasurer.exe  "w:/A Quiet Place/BDMV/index.bdmv"
    w:\A Quiet Place\BDMV\PLAYLIST\00800.mpls

Using a directory name

    $ madmeasurer.exe  "w:/A Quiet Place"
    w:\A Quiet Place\BDMV\PLAYLIST\00800.mpls

Note that using `-d0` will make this approach execute more swiftly 

### To copy an existing index.bdmv.measurements so BD folder playback will pick up the measurements file

`-v` is used in this example in order to illustrate what has happened.

    $ madmeasurer.exe -d0 -v -c "w:/A Quiet Place"
    2019-04-04 22:05:58,104 - Copying w:\A Quiet Place\BDMV\index.bdmv.measurements to w:\A Quiet Place\BDMV\PLAYLIST\00800.mpls.measurements 
    2019-04-04 22:06:30,717 - Copied w:\A Quiet Place\BDMV\index.bdmv.measurements to w:\A Quiet Place\BDMV\PLAYLIST\00800.mpls.measurements
    2019-04-04 22:06:30,718 - Processed 1 BDs found in w:/A Quiet Place/BDMV/index.bdmv

If the measurements file exists already, the file is not copied a 2nd time

    $ madmeasurer.exe -d0 -vv -c "w:/A Quiet Place"
    2019-04-04 22:07:10,718 - Searching w:/A Quiet Place/BDMV/index.bdmv
    2019-04-04 22:07:10,816 - Opening w:\A Quiet Place
    2019-04-04 22:07:10,901 - Ignoring : w:\A Quiet Place\BDMV\PLAYLIST\00800.mpls.measurements exists and force=False
    2019-04-04 22:07:10,901 - Closing w:\A Quiet Place
    2019-04-04 22:07:10,902 - Processed 1 BDs found in w:/A Quiet Place/BDMV/index.bdmv

Use `-f` to override this

    $ madmeasurer.exe -d0 -vv -c -f "w:/A Quiet Place"
    2019-04-04 22:08:50,085 - Searching w:/A Quiet Place/BDMV/index.bdmv
    2019-04-04 22:08:50,195 - Opening w:\A Quiet Place
    2019-04-04 22:08:51,444 - Overwriting : w:\A Quiet Place\BDMV\index.bdmv.measurements with w:\A Quiet Place\BDMV\PLAYLIST\00800.mpls.measurements as force=True
    2019-04-04 22:08:51,444 - Copying w:\A Quiet Place\BDMV\index.bdmv.measurements to w:\A Quiet Place\BDMV\PLAYLIST\00800.mpls.measurements
    2019-04-04 22:09:23,285 - Copied w:\A Quiet Place\BDMV\index.bdmv.measurements to w:\A Quiet Place\BDMV\PLAYLIST\00800.mpls.measurements
    2019-04-04 22:09:23,286 - Closing w:\A Quiet Place
    2019-04-04 22:09:23,286 - Processed 1 BDs found in w:/A Quiet Place/BDMV/index.bdmv

### Measuring playlists

Note that `--dry-run` is used in these examples.

#### Locating madMeasureHDR.exe

`madMeasureHDR.exe` can be found in one of 3 ways

  1) set on the command line using `--mad-measure-path` 
  2) set an environment variable named `MAD_MEASURE_HDR_PATH`
  3) put the directory on your PATH
  
Note this value can be the directory containing the exe or the full path to the exe. 

#### Basic Example

    $ madmeasurer.exe -d0 -vv -m --dry-run "w:/A Quiet Place"
    2019-04-04 22:27:52,991 - Searching w:/A Quiet Place/BDMV/index.bdmv
    2019-04-04 22:27:53,121 - Opening w:\A Quiet Place
    2019-04-04 22:27:54,260 - Measuring : w:\A Quiet Place\BDMV\PLAYLIST\00800.mpls.measurements does not exist
    2019-04-04 22:27:54,261 - DRY RUN! Triggering : ['C:\\Users\\mattk\\AppData\\Roaming\\J River\\Media Center 25\\Plugins\\madvr\\madMeasureHDR.exe', 'w:\\A Quiet Place\\BDMV\\PLAYLIST\\00800.mpls']
    2019-04-04 22:27:54,262 - Closing w:\A Quiet Place
    2019-04-04 22:27:54,262 - Processed 1 BD found in w:/A Quiet Place/BDMV/index.bdmv

#### When the measurements file already exists 

No further action is taken

    $ madmeasurer.exe -d0 -vv -m "w:/A Quiet Place"
    2019-04-04 22:10:52,451 - Searching w:/A Quiet Place/BDMV/index.bdmv
    2019-04-04 22:10:52,554 - Opening w:\A Quiet Place
    2019-04-04 22:10:52,631 - Ignoring : w:\A Quiet Place\BDMV\PLAYLIST\00800.mpls.measurements exists, force is false
    2019-04-04 22:10:52,632 - Closing w:\A Quiet Place
    2019-04-04 22:10:52,633 - Processed 1 BDs found in w:/A Quiet Place/BDMV/index.bdmv

#### Forcing remeasurement

Use `-f` 

    $ madmeasurer.exe -d0 -vv -m -f --dry-run "w:/A Quiet Place"
    2019-04-04 22:22:55,456 - Searching w:/A Quiet Place/BDMV/index.bdmv
    2019-04-04 22:22:55,576 - Opening w:\A Quiet Place
    2019-04-04 22:22:56,869 - Remeasuring : w:\A Quiet Place\BDMV\PLAYLIST\00800.mpls.measurements exists, force is true
    2019-04-04 22:22:56,870 - DRY RUN! Triggering : ['C:\\Users\\mattk\\AppData\\Roaming\\J River\\Media Center 25\\Plugins\\madvr\\madMeasureHDR.exe', 'w:\\A Quiet Place\\BDMV\\PLAYLIST\\00800.mpls']
    2019-04-04 22:22:56,870 - Closing w:\A Quiet Place
    2019-04-04 22:22:56,871 - Processed 1 BD found in w:/A Quiet Place/BDMV/index.bdmv

#### Measuring all playlists of a minimum duration

Use `--measure-all-playlists` (perhaps with `--min-duration` if the default of 30mins is too long)

    $ madmeasurer.exe -d0 -vv -m --measure-all-playlists --min-duration 1 --dry-run "w:/A Quiet Place"
    2019-04-04 22:29:39,192 - Searching w:/A Quiet Place/BDMV/index.bdmv
    2019-04-04 22:29:39,301 - Opening w:\A Quiet Place
    2019-04-04 22:29:39,493 - Measurement candidate w:\A Quiet Place - 00001.mpls : length is 00:03:00.180
    2019-04-04 22:29:39,494 - Measuring : w:\A Quiet Place\BDMV\PLAYLIST\00001.mpls.measurements does not exist
    2019-04-04 22:29:39,494 - DRY RUN! Triggering : ['C:\\Users\\mattk\\AppData\\Roaming\\J River\\Media Center 25\\Plugins\\madvr\\madMeasureHDR.exe', 'w:\\A Quiet Place\\BDMV\\PLAYLIST\\00001.mpls']
    2019-04-04 22:29:39,679 - Measurement candidate w:\A Quiet Place - 00035.mpls : length is 00:01:50.109
    2019-04-04 22:29:39,680 - Measuring : w:\A Quiet Place\BDMV\PLAYLIST\00035.mpls.measurements does not exist
    2019-04-04 22:29:39,680 - DRY RUN! Triggering : ['C:\\Users\\mattk\\AppData\\Roaming\\J River\\Media Center 25\\Plugins\\madvr\\madMeasureHDR.exe', 'w:\\A Quiet Place\\BDMV\\PLAYLIST\\00035.mpls']
    2019-04-04 22:29:39,685 - Measuring : w:\A Quiet Place\BDMV\PLAYLIST\00800.mpls.measurements does not exist
    2019-04-04 22:29:39,685 - DRY RUN! Triggering : ['C:\\Users\\mattk\\AppData\\Roaming\\J River\\Media Center 25\\Plugins\\madvr\\madMeasureHDR.exe', 'w:\\A Quiet Place\\BDMV\\PLAYLIST\\00800.mpls']
    2019-04-04 22:29:39,686 - Closing w:\A Quiet Place
    2019-04-04 22:29:39,686 - Processed 1 BD found in w:/A Quiet Place/BDMV/index.bdmv

### Controlling the Search 

#### Searching Multiple Locations

Just pass more than 1 path

    $ madmeasurer.exe -d0 -v -m --dry-run "w:/A Quiet Place" "W:\Avengers_ Infinity War"
    2019-04-04 22:31:32,795 - DRY RUN! Triggering : ['C:\\Users\\mattk\\AppData\\Roaming\\J River\\Media Center 25\\Plugins\\madvr\\madMeasureHDR.exe', 'w:\\A Quiet Place\\BDMV\\PLAYLIST\\00800.mpls']
    2019-04-04 22:31:32,796 - Processed 1 BD found in w:/A Quiet Place/BDMV/index.bdmv
    2019-04-04 22:31:33,878 - Processed 1 BD found in W:\Avengers_ Infinity War/BDMV/index.bdmv
    
#### Using Wildcards

With wildcards in the supplied path 

    $ madmeasurer.exe -d0 -vv -m --dry-run "w:/Al*n*"
    2019-04-04 22:33:46,050 - Searching w:/Al*n*/BDMV/index.bdmv
    2019-04-04 22:33:46,373 - Opening w:\Alice in Wonderland
    2019-04-04 22:33:48,015 - Closing w:\Alice in Wonderland
    2019-04-04 22:33:48,016 - Opening w:\Aliens
    2019-04-04 22:33:51,605 - Closing w:\Aliens
    2019-04-04 22:33:51,606 - Opening w:\Alien_ Resurrection
    2019-04-04 22:33:54,065 - Closing w:\Alien_ Resurrection
    2019-04-04 22:33:54,066 - Opening w:\Alien³
    2019-04-04 22:33:57,103 - Closing w:\Alien³
    2019-04-04 22:33:57,104 - Processed 4 BDs found in w:/Al*n*/BDMV/index.bdmv

Searching at a specific depth with `-d`

    $ madmeasurer.exe -d1 -vv -m --dry-run "w:"
    2019-04-04 22:34:50,766 - Searching w:/*/BDMV/index.bdmv

Searching recursively through an entire path 

    $ madmeasurer.exe -vv -m --dry-run "w:"
    2019-04-04 22:35:26,468 - Searching w:/**/BDMV/index.bdmv
    
## Working with ISOs

All of the previous options work with iso files instead by passing `-i`
    
    $ madmeasurer.exe -vv -m -d1 --dry-run -i "w:"
    2019-04-04 22:42:50,057 - Searching w:/*/*.iso
    2019-04-04 22:43:04,927 - Opening w:/isos\test.iso
    2019-04-04 22:43:08,356 - Mounted w:\isos\test.iso on D:\
    2019-04-04 22:43:08,644 - Ignoring : D:\BDMV\PLAYLIST\00800.mpls.measurements exists, force is false
    2019-04-04 22:43:11,132 - Dismounted w:\isos\test.iso
    2019-04-04 22:43:11,138 - Closing w:/isos\test.iso
    2019-04-04 22:43:11,138 - Opening w:/isos\test2.iso
    2019-04-04 22:43:14,649 - Mounted w:\isos\test2.iso on D:\
    2019-04-04 22:43:14,926 - Ignoring : D:\BDMV\PLAYLIST\00800.mpls.measurements exists, force is false
    2019-04-04 22:43:17,705 - Dismounted w:\isos\test2.iso
    2019-04-04 22:43:17,767 - Closing w:/isos\test2.iso
    2019-04-04 22:43:17,769 - Processed 2 BDs found in w:/*/*.iso

Note that the ISO will be mounted using a `PowerShell` cmdlet (`Mount-DiskImage`) and measurements file will be written into the ISO.

## Running Locally

* add deps to PYTHONPATH and PATH?

## Debugging libbluray

set environment variables as follows

    set BD_DEBUG_FILE=/some/file.log
    set BD_DEBUG_MASK=0x00100
    
debug mask values are shown in https://code.videolan.org/videolan/libbluray/blob/master/src/util/log_control.h#L31


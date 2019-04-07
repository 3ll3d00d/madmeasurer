from contextlib import contextmanager
import platform
import os
import subprocess
from madmeasurer.loggers import main_logger


@contextmanager
def mount_if_necessary(bd_path, args):
    '''
    A context manager that can mount and iso and return the mounted path then dismounts afterwards.
    '''
    target = bd_path
    mounted = False
    main_requires_mount = args.main_by_mpc_be is True or args.analyse_main_algos is True or args.main_by_jriver is True or args.main_by_jriver_extended is True
    if args.measure is True or args.copy is True or main_requires_mount is True or args.describe_bd is True:
        mounted = target[-4:] == '.iso'
        if mounted is True:
            if platform.system() == "Windows":
                target = mount_iso_on_windows(bd_path)
                if target is not None:
                    if not os.path.exists(f"{target}BDMV/index.bdmv"):
                        main_logger.error(f"{bd_path} does not contain a BD folder")
                        target = None
            elif platform.system() == "Linux":
                pass
    try:
        yield target
    finally:
        if mounted:
            if platform.system() == "Windows":
                dismount_iso_on_windows(bd_path)
            elif platform.system() == "Linux":
                pass


def mount_iso_on_windows(iso):
    '''
    Mounts ISO and returns the mounted drive path.
    :param iso: the iso.
    :return: the mounted path.
    '''
    iso_to_mount = os.path.abspath(iso)
    command = f"PowerShell ((Mount-DiskImage {iso_to_mount} -PassThru) | Get-Volume).DriveLetter"
    main_logger.debug(f"Triggering : {command}")
    result = subprocess.run(command, capture_output=True)
    if result is not None and result.returncode == 0:
        target = f"{result.stdout.decode('utf-8').rstrip()}:{os.path.sep}"
        main_logger.info(f"Mounted {iso_to_mount} on {target}")
    else:
        main_logger.error(f"Unable to mount {iso_to_mount} , stdout: {result.stdout.decode('utf-8')}, stderr: {result.stderr.decode('utf-8')}")
        target = None
    return target


def dismount_iso_on_windows(iso):
    '''
    Dismounts the ISO.
    :param iso: the iso.
    '''
    iso_to_dismount = os.path.abspath(iso)
    command = f"PowerShell Dismount-DiskImage {iso_to_dismount}"
    main_logger.debug(f"Triggering : {command}")
    result = subprocess.run(command, capture_output=True)
    if result is not None and result.returncode == 0:
        main_logger.info(f"Dismounted {iso_to_dismount}")
    else:
        main_logger.error(f"Unable to dismount {iso_to_dismount} , stdout: {result.stdout.decode('utf-8')}, stderr: {result.stderr.decode('utf-8')}")


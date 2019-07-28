# -*- mode: python -*-
import os

# work-around for https://github.com/pyinstaller/pyinstaller/issues/4064
import distutils

distutils_dir = getattr(distutils, 'distutils_path', None)
if distutils_dir is not None and distutils_dir.endswith('__init__.py'):
    distutils.distutils_path = os.path.dirname(distutils.distutils_path)


# helper functions
block_cipher = None
spec_root = os.path.abspath(SPECPATH)

a = Analysis(['madmeasurer/__main__.py'],
             pathex=[spec_root],
             binaries=[],
             datas=[
                ('deps\\bluray.dll', '.'),
             ],
             hiddenimports=[],
             hookspath=['.\\hooks\\'],
             runtime_hooks=[],
             excludes=['pkg_resources'],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,
          name='madmeasurer',
          debug=False,
          strip=False,
          upx=False,
          runtime_tmpdir=None,
          console=True)

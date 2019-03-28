# -*- mode: python -*-

block_cipher = None

a = Analysis(['madmeasurer.py'],
             pathex=['C:\\Users\\mattk\\github\\madmeasurer'],
             binaries=None,
             datas=[
                ('deps\\bluray.dll', '.'),
                ('deps\\libbluray-j2se-1.0.2.jar', '.')
             ],
             hiddenimports=[],
             hookspath=[],
             runtime_hooks=[],
             excludes=[],
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
          console=True)

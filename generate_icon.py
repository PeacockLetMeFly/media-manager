"""Generate icon.ico for use by PyInstaller at build time."""
from icon_gen import make_icon

img = make_icon('disconnected', size=256)
img.save('icon.ico', format='ICO')
print('icon.ico generated')

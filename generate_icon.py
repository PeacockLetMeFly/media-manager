"""Generate icon.ico for use by PyInstaller at build time."""
from icon_gen import make_icon

sizes = [16, 24, 32, 48, 64, 128, 256]
images = [make_icon('disconnected', size=s) for s in sizes]
images[0].save('icon.ico', format='ICO', sizes=[(s, s) for s in sizes],
               append_images=images[1:])
print('icon.ico generated')

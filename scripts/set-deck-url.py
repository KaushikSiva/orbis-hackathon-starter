"""Set the deployed studio link and regenerate its QR code in the editable deck."""
import re
import sys
from pathlib import Path
from urllib.parse import urlparse
import qrcode
import zxingcpp
from PIL import Image

root=Path(__file__).resolve().parents[1]
if len(sys.argv)!=2:
    raise SystemExit('Usage: python scripts/set-deck-url.py https://your-studio.onrender.com')
url=sys.argv[1].rstrip('/')
parsed=urlparse(url)
if parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
    raise SystemExit('Use a plain HTTPS studio URL with no credentials or query parameters.')
path=root/'docs/deck/showroom-deck.html'
html=path.read_text()
for element in ('deployment-link','qr-link'):
    html,count=re.subn(r'(id="'+element+r'" href=")[^"]*(")',lambda m:m[1]+url+m[2],html)
    if count!=1:raise SystemExit('Expected one '+element+' in the editable deck.')
html=re.sub(r'(<a id="deployment-link"[^>]*>)[^<]*(</a>)',lambda m:m[1]+parsed.netloc+parsed.path+m[2],html)
qr=qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M,box_size=12,border=4)
qr.add_data(url);qr.make(fit=True)
image=qr.make_image(fill_color='#26352b',back_color='white').convert('RGB')
assert zxingcpp.read_barcode(image).text==url
image.save(root/'docs/deck/render-qr.png')
path.write_text(html)
print('Updated the deck URL and verified its QR code.')

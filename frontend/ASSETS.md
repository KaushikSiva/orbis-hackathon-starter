# SHOWROOM visual assets

## Sample room reference

`public/images/sample-room.jpg` is an externally sourced room reference from Unsplash, downloaded on September 12, 2026:

- [Exact source image](https://images.unsplash.com/photo-1600210492486-724fe5c67fb0?auto=format&fit=crop&w=2000&q=90)
- [Unsplash license](https://unsplash.com/license)
- Source image identifier: `photo-1600210492486-724fe5c67fb0`.

The sample is labeled **SAMPLE ROOM · REFERENCE** in the interface. It is not an Orbis generation, a result of a redesign, or evidence of a live stream. User uploads replace this reference. Browser preparation center-crops an uploaded image to the model's 1280 × 736 aspect ratio before sending it to Reactor; the original uploaded image stays in application storage.

Product reference images come from the retailer URLs in `../backend/catalog.json`. Each product includes its retailer link, published price, and dimensions. These product images substantiate the shopping list; they are not extracted from generated video.

## Interface

- Fonts: Manrope and DM Sans, loaded from Google Fonts. System sans-serif is the offline fallback.
- Icons: Lucide React (ISC license).
- Logo: original SHOWROOM wordmark composition and simple architectural mark, created for this application; `public/favicon.svg` is an original vector asset.
- No AI-generated still images are included in the frontend.

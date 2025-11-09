# Notes on the `tools/` code:

## Video Compression

- Move to the tools dir:
  `cd tools`
- Make the script executable: `chmod +x compress_videos.sh`
- Provide input and output folders: `./compress_videos.sh ../videos/raw ../videos/compressed`
- Videos already compressed in the output dir are automatically skipped.

## Image Conversion to WebP

- Move to the tools dir:
  `cd tools`
- Make the script executable: `chmod +x convert_to_webp.sh`
- Provide input and output folders: `./convert_to_webp.sh ../images/original ../images/webp`
- Images already in WebP format in the output dir are automatically skipped.

## Video Conversion to GIF

- Move to the tools dir:
  `cd tools`
- Make the script executable: `chmod +x convert_to_gif.sh`
- Provide input and output folders: `./convert_to_gif.sh ../videos/compressed ../videos/gif`
- Videos already in GIF format in the output dir are automatically skipped.

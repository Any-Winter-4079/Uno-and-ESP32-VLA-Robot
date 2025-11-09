#!/bin/bash

# check if cwebp is installed
if ! command -v cwebp &> /dev/null
then
    echo "cwebp is not installed. Please install it using 'brew install webp'"
    exit 1
fi

# check if input and output directories are provided
if [ $# -ne 2 ]; then
    echo "Usage: $0 <input_folder> <output_folder>"
    exit 1
fi

INPUT_DIR="$1"
OUTPUT_DIR="$2"

# create output directory if it doesn't exist
mkdir -p "$OUTPUT_DIR"

# set quality (0-100; higher is better but also larger)
QUALITY=100

# process each PNG and JPG file in the input directory
for input_file in "$INPUT_DIR"/*.{png,jpg,jpeg}; do
    # get the filename without path and extension
    filename=$(basename "${input_file%.*}")
    
    # convert image to WEBP if WEBP version does not exist
    if [ ! -f "$OUTPUT_DIR/${filename}.webp" ]; then
        echo "Converting $filename to WebP..."
        
        cwebp -q $QUALITY -m 6 -af -f 100 -sharpness 0 -mt -v "$input_file" -o "$OUTPUT_DIR/${filename}.webp"
        
        echo "Conversion complete for $filename"
    else
        echo "WebP version of $filename already exists (skipped)"
    fi
done

echo "All images processed"
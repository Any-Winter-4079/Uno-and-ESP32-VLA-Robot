#!/bin/bash

# check if FFmpeg is installed
if ! command -v ffmpeg &> /dev/null
then
    echo "FFmpeg is not installed. Please install it using 'brew install ffmpeg'"
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

# process each MP4 file in the input directory
for input_file in "$INPUT_DIR"/*.mp4; do
    # get the filename without path
    filename=$(basename "$input_file")
    
    # compress video if compressed version does not exist
    if [ ! -f "$OUTPUT_DIR/$filename" ]; then
        echo "Compressing $filename..."

        ffmpeg -i "$input_file" \
            -vf "scale=640:-2" \
            -c:v libx264 \
            -crf 26 \
            -preset medium \
            -profile:v high \
            -level 4.1 \
            -movflags +faststart \
            -pix_fmt yuv420p \
            -color_primaries bt2020 \
            -color_trc arib-std-b67 \
            -colorspace bt2020nc \
            -color_range tv \
            -x264-params "colorprim=bt2020:transfer=arib-std-b67:colormatrix=bt2020nc" \
            -c:a aac \
            -b:a 96k \
            "$OUTPUT_DIR/${filename%.*}.mp4"

        
        echo "Compression complete for $filename"
    else
        echo "Compressed version of $filename already exists (skipped)"
    fi
done

echo "All videos processed"
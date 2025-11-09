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
    # get the filename without path and extension
    filename=$(basename "${input_file%.*}")
    
    # convert video to GIF if GIF version does not exist
    if [ ! -f "$OUTPUT_DIR/$filename.gif" ]; then
        echo "Converting $filename to GIF..."
        
        ffmpeg -i "$input_file" \
            -vf "fps=16,scale=320:-1:flags=lanczos,split[s0][s1];[s0]palettegen=max_colors=256:stats_mode=full[p];[s1][p]paletteuse=dither=bayer:bayer_scale=2:diff_mode=rectangle" \
            -loop 0 \
            -color_primaries bt2020 \
            -color_trc arib-std-b67 \
            -colorspace bt2020nc \
            -color_range tv \
            "$OUTPUT_DIR/${filename%.*}.gif"
        
        echo "Conversion complete for $filename"
    else
        echo "GIF version of $filename already exists (skipped)"
    fi
done

echo "All videos processed"
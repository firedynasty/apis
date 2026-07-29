#!/bin/bash
# Upload files to a OneNote section.
# - Single file: uploaded as its own page (title = filename)
# - Multiple files: bundled into one page, prompts for title (default = first filename)
# - Folder: each folder becomes its own page via upload-folder
# Usage: onenote_upload_files.sh file1 file2 ...

export PATH="/usr/local/bin:/opt/homebrew/bin:$PATH"

ONENOTE="/Users/stanleytan/Documents/technical/github/apis/apis_microsoft/onenote_signin.py"
MD_TO_HTML="/Users/stanleytan/Documents/technical/python/convert_html_to_docx/02evernote/mdToHtml.py"

# Prompt for section ID with clipboard pre-filled
SECTION_ID=$(osascript -e 'try
    set clipContent to the clipboard
on error
    set clipContent to ""
end try
text returned of (display dialog "Paste OneNote section ID:" default answer clipContent buttons {"Cancel", "Upload"} default button "Upload" with title "Send to OneNote")' 2>/dev/null)

SECTION_ID=$(echo "$SECTION_ID" | tr -d '\r\n ')

if [ -z "$SECTION_ID" ]; then
    echo "Cancelled."
    exit 0
fi

# Prompt for optional prefix (leave blank to skip)
PREFIX=$(osascript -e 'text returned of (display dialog "Page title prefix (optional):" default answer "" buttons {"Skip", "OK"} default button "OK" with title "Send to OneNote")' 2>/dev/null)
PREFIX=$(echo "$PREFIX" | tr -d '\r\n')

echo "Uploading to section: $SECTION_ID"
[ -n "$PREFIX" ] && echo "Prefix: $PREFIX"
echo ""

# Separate folders and files
FOLDERS=()
FILES=()
for filepath in "$@"; do
    if [ -d "$filepath" ]; then
        FOLDERS+=("$filepath")
    else
        FILES+=("$filepath")
    fi
done

# --- Folders: each uploads as its own page ---
for folderpath in "${FOLDERS[@]}"; do
    foldername=$(basename "$folderpath")
    folder_title="$foldername"
    [ -n "$PREFIX" ] && folder_title="$PREFIX - $foldername"
    echo "Uploading folder '$folder_title'..."
    python3 "$ONENOTE" upload-folder "$folderpath" --title "$folder_title" --section "$SECTION_ID"
    sleep 2
done

# --- Files ---
if [ ${#FILES[@]} -eq 0 ]; then
    echo "Done."
    exit 0
fi

if [ ${#FILES[@]} -eq 1 ]; then
    # Single file — upload as its own page, title = filename (no extension)
    filepath="${FILES[0]}"
    filename=$(basename "$filepath")
    ext="${filename##*.}"
    ext=$(echo "$ext" | tr '[:upper:]' '[:lower:]')
    title="${filename%.*}"

    [ -n "$PREFIX" ] && title="$PREFIX - $title"

    case "$ext" in
        md)
            tmpfile="/tmp/onenote_upload_$$.html"
            echo "Converting $filename → HTML..."
            python3 "$MD_TO_HTML" "$filepath" "$tmpfile"
            if [ -f "$tmpfile" ]; then
                python3 "$ONENOTE" upload "$tmpfile" --title "$title" --section "$SECTION_ID"
                rm -f "$tmpfile"
            else
                echo "FAILED: $filename — md conversion failed"
            fi
            ;;
        txt|csv|html|htm|docx)
            python3 "$ONENOTE" upload "$filepath" --title "$title" --section "$SECTION_ID"
            ;;
        *)
            echo "SKIPPED: $filename — unsupported format"
            ;;
    esac
else
    # Multiple files — bundle into one page
    # Default title = first filename (no extension)
    first_filename=$(basename "${FILES[0]}")
    default_title="${first_filename%.*}"
    [ -n "$PREFIX" ] && default_title="$PREFIX - $default_title"

    PAGE_TITLE=$(osascript -e "text returned of (display dialog \"Page title for bundled upload:\" default answer \"$default_title\" buttons {\"Cancel\", \"Upload\"} default button \"Upload\" with title \"Send to OneNote\")" 2>/dev/null)

    if [ -z "$PAGE_TITLE" ]; then
        echo "Cancelled."
        exit 0
    fi

    # Convert any .csv files to temp .txt copies so the bundler accepts them
    CONVERTED_TMPS=()
    UPLOAD_FILES=()
    for f in "${FILES[@]}"; do
        fext="${f##*.}"
        fext=$(echo "$fext" | tr '[:upper:]' '[:lower:]')
        if [ "$fext" = "csv" ]; then
            tmpcsv="/tmp/onenote_csv_$$.$(basename "${f%.csv}").txt"
            cp "$f" "$tmpcsv"
            CONVERTED_TMPS+=("$tmpcsv")
            UPLOAD_FILES+=("$tmpcsv")
        else
            UPLOAD_FILES+=("$f")
        fi
    done

    echo "Bundling ${#UPLOAD_FILES[@]} file(s) into page '$PAGE_TITLE'..."
    python3 "$ONENOTE" upload-files --title "$PAGE_TITLE" --section "$SECTION_ID" "${UPLOAD_FILES[@]}"

    # Clean up temp csv→txt copies
    for t in "${CONVERTED_TMPS[@]}"; do rm -f "$t"; done
fi

echo ""
echo "Done."

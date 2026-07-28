
# OneNote CLI (Microsoft Graph fAPI)
_ONENOTE=/Users/stanleytan/Documents/technical/apis_microsoft/onenote_signin.py

onenote-login() {
    python3 "$_ONENOTE" login
}

onenote-notebooks() {
    python3 "$_ONENOTE" notebooks
}

onenote-sections() {
    python3 "$_ONENOTE" sections "$@"
}

onenote-pages() {
    python3 "$_ONENOTE" pages "$@"
}

onenote-read() {
    python3 "$_ONENOTE" download "$1" | python3 -c "
import sys, html, re
raw = sys.stdin.read()
# extract title
t = re.search(r'<title>(.*?)</title>', raw)
if t: print(t.group(1)); print('---')
# extract links with their text
body = re.search(r'<body[^>]*>(.*)</body>', raw, re.S)
if not body: sys.exit()
text = body.group(1)
# replace <a href=url>text</a> with text (url)
text = re.sub(r'<a[^>]*href=\"([^\"]+)\"[^>]*>(.*?)</a>', r'\2 (\1)', text)
# replace <br> and block tags with newlines
text = re.sub(r'<br\s*/?>','\n', text)
text = re.sub(r'</?(p|div|h[1-6]|li|tr)[^>]*>', '\n', text)
# strip remaining tags
text = re.sub(r'<[^>]+>', '', text)
# unescape html entities
text = html.unescape(text)
# convert literal \\n sequences to actual newlines
text = text.replace('\\\\n', '\\n').replace('\\n', '\n\n')
# clean up blank lines, collapsing multiple consecutive blanks to one
lines = [l.strip() for l in text.splitlines()]
output = '\n'.join(lines)
output = re.sub(r'\n{3,}', '\n\n', output)
print(output.strip())
"
}

onenote-new() {
    local section_id="$1"
    local title="$2"
    local tmpfile
    tmpfile=$(mktemp /tmp/onenote_newXXXXXX)

    echo "Opening in Sublime Text... (paste your content, save, then close)"
    "/Applications/Sublime Text.app/Contents/SharedSupport/bin/subl" --wait "$tmpfile"

    # Strip markdown formatting if present (**, ##, etc.)
    if pandoc --from markdown --to plain --no-highlight --wrap=none "$tmpfile" -o "${tmpfile}.plain" 2>/dev/null && [ -s "${tmpfile}.plain" ]; then
        mv "${tmpfile}.plain" "$tmpfile"
    fi

    printf "Upload '%s' to OneNote? (y/n): " "$title"
    read -r confirm
    if [ "$confirm" = "y" ] || [ "$confirm" = "Y" ]; then
        python3 "$_ONENOTE" upload "$tmpfile" --title "$title" --section "$section_id"
    else
        echo "Discarded."
    fi
    rm -f "$tmpfile"
}

onenote-edit() {
    local page_id="$1"
    local tmpfile
    tmpfile=$(mktemp /tmp/onenote_editXXXXXX)

    # Download and convert to readable text (same pipeline as onenote-read)
    python3 "$_ONENOTE" download "$page_id" | python3 -c "
import sys, html, re
raw = sys.stdin.read()
t = re.search(r'<title>(.*?)</title>', raw)
if t: print(t.group(1)); print('---')
body = re.search(r'<body[^>]*>(.*)</body>', raw, re.S)
if not body: sys.exit()
text = body.group(1)
text = re.sub(r'<a[^>]*href=\"([^\"]+)\"[^>]*>(.*?)</a>', r'\2 (\1)', text)
text = re.sub(r'<br\s*/?>', '\n', text)
text = re.sub(r'</?(p|div|h[1-6]|li|tr)[^>]*>', '\n', text)
text = re.sub(r'<[^>]+>', '', text)
text = html.unescape(text)
text = text.replace('\\\\n', '\\n').replace('\\n', '\n\n')
lines = [l.strip() for l in text.splitlines()]
output = '\n'.join(lines)
output = re.sub(r'\n{3,}', '\n\n', output)
print(output.strip())
" > "$tmpfile"

    echo "Opening in Sublime Text... (close the file when done)"
    "/Applications/Sublime Text.app/Contents/SharedSupport/bin/subl" --wait "$tmpfile"

    # Strip markdown formatting if present (**, ##, etc.)
    if pandoc --from markdown --to plain --no-highlight --wrap=none "$tmpfile" -o "${tmpfile}.plain" 2>/dev/null && [ -s "${tmpfile}.plain" ]; then
        mv "${tmpfile}.plain" "$tmpfile"
    fi

    printf "Save changes back to OneNote? (y/n): "
    read -r confirm
    if [ "$confirm" = "y" ] || [ "$confirm" = "Y" ]; then
        python3 "$_ONENOTE" update "$page_id" "$tmpfile"
    else
        echo "Discarded."
    fi
    rm -f "$tmpfile"
}

onenote-download() {
    python3 "$_ONENOTE" download "$@"
}

onenote-upload() {
    python3 "$_ONENOTE" upload "$@"
}

onenote-browse() {
    local ids=()
    local names=()

    # Load notebooks
    while IFS=$'\t' read -r id name; do
        [ -z "$id" ] && continue
        ids+=("$id")
        names+=("$name")
    done < <(python3 "$_ONENOTE" notebooks)

    if [ ${#ids[@]} -eq 0 ]; then
        echo "No notebooks found (are you logged in?)"
        return 1
    fi

    # Show notebooks
    while true; do
        echo ""
        echo "📓 Notebooks"
        echo ""
        for i in $(seq 1 ${#ids[@]}); do
            printf "%3d  📓 %s\n" "$i" "${names[$i]}"
        done
        echo ""
        printf "Enter number (q = quit): "
        read -r choice
        [ "$choice" = "q" ] || [ "$choice" = "Q" ] && return 0
        if [[ "$choice" =~ ^[0-9]+$ ]] && [ "$choice" -ge 1 ] && [ "$choice" -le "${#ids[@]}" ]; then
            _onenote_sections "${ids[$choice]}" "${names[$choice]}"
        fi
    done
}

_onenote_sections() {
    local notebook_id="$1"
    local notebook_name="$2"
    local ids=()
    local names=()

    while IFS=$'\t' read -r id name; do
        [ -z "$id" ] && continue
        ids+=("$id")
        names+=("$name")
    done < <(python3 "$_ONENOTE" sections "$notebook_id")

    if [ ${#ids[@]} -eq 0 ]; then
        echo "No sections in this notebook"
        return
    fi

    while true; do
        echo ""
        echo "📓 $notebook_name → Sections"
        echo ""
        for i in $(seq 1 ${#ids[@]}); do
            printf "%3d  📂 %s\n" "$i" "${names[$i]}"
        done
        echo ""
        printf "Enter number (c<n> = copy section id, .. = back, q = quit): "
        read -r choice
        [ "$choice" = "q" ] || [ "$choice" = "Q" ] && return 0
        [ "$choice" = ".." ] && return
        if [[ "$choice" =~ ^c[0-9]+$ ]]; then
            local num="${choice#c}"
            if [ "$num" -ge 1 ] && [ "$num" -le "${#ids[@]}" ]; then
                echo "${ids[$num]}" | pbcopy
                echo "Copied section id for '${names[$num]}' to clipboard"
            fi
        elif [[ "$choice" =~ ^[0-9]+$ ]] && [ "$choice" -ge 1 ] && [ "$choice" -le "${#ids[@]}" ]; then
            _onenote_pages "${ids[$choice]}" "${names[$choice]}" "$notebook_name"
        fi
    done
}

_onenote_pages() {
    local section_id="$1"
    local section_name="$2"
    local notebook_name="$3"
    local ids=()
    local names=()

    while IFS=$'\t' read -r id name; do
        [ -z "$id" ] && continue
        ids+=("$id")
        names+=("$name")
    done < <(python3 "$_ONENOTE" pages "$section_id")

    if [ ${#ids[@]} -eq 0 ]; then
        echo "No pages in this section"
        return
    fi

    while true; do
        echo ""
        echo "📓 $notebook_name → 📂 $section_name → Pages"
        echo ""
        for i in $(seq 1 ${#ids[@]}); do
            printf "%3d  📄 %s\n" "$i" "${names[$i]}"
        done
        echo ""
        printf "Enter number to read (n = new, e <n> = edit, d <n> = download, c = copy section id, .. = back, q = quit): "
        read -r choice
        choice="${choice// /}"
        [ "$choice" = "q" ] || [ "$choice" = "Q" ] && return 0
        [ "$choice" = ".." ] && return
        if [ "$choice" = "n" ] || [ "$choice" = "N" ]; then
            printf "Page title: "
            read -r new_title
            [ -z "$new_title" ] && echo "No title entered." && continue
            onenote-new "$section_id" "$new_title"
        elif [ "$choice" = "c" ] || [ "$choice" = "C" ]; then
            echo "$section_id" | pbcopy
            echo "Copied section id for '$section_name' to clipboard"
        elif [[ "$choice" =~ ^e[0-9]+$ ]]; then
            local num="${choice#e}"
            if [ "$num" -ge 1 ] && [ "$num" -le "${#ids[@]}" ]; then
                onenote-edit "${ids[$num]}"
            fi
        elif [[ "$choice" =~ ^d[0-9]+$ ]]; then
            local num="${choice#d}"
            if [ "$num" -ge 1 ] && [ "$num" -le "${#ids[@]}" ]; then
                local default_name="${names[$num]}.html"
                printf "Save as [%s]: " "$default_name"
                read -r outfile
                [ -z "$outfile" ] && outfile="$default_name"
                python3 "$_ONENOTE" download "${ids[$num]}" "$outfile"
                echo "Downloaded to: $outfile"
            fi
        elif [[ "$choice" =~ ^[0-9]+$ ]] && [ "$choice" -ge 1 ] && [ "$choice" -le "${#ids[@]}" ]; then
            echo ""
            echo "━━━ ${names[$choice]} ━━━"
            onenote-read "${ids[$choice]}"
            echo "━━━━━━━━━━━━━━━━━━━━━━━━━"
        fi
    done
}


import re

with open(r'd:\DeepScribe\novel_translator\app.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Find the corrupted line that starts with return """ followed by SortableJS code
old_marker = '    return """function o(t)'
idx = content.find(old_marker)
if idx >= 0:
    # Find the <style> tag that should come right after the triple-quote opening
    style_marker = '\n    <style>'
    newline_after = content.find(style_marker, idx)
    if newline_after >= 0:
        corrupted_section = content[idx:newline_after]
        content = content[:idx] + '    return """\n' + content[newline_after:]
        with open(r'd:\DeepScribe\novel_translator\app.py', 'w', encoding='utf-8') as f:
            f.write(content)
        print(f'Fixed: removed {len(corrupted_section)} chars of leftover SortableJS code')
    else:
        print('Could not find style tag end marker')
else:
    print('Pattern not found - may already be fixed')

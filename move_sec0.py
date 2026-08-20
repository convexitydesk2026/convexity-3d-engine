import sys

with open('dashboard_pro.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

start_idx = -1
end_idx = -1
for i, line in enumerate(lines):
    if '# --- SECTION 0: UNIFIED ESTATE CALENDAR ---' in line:
        start_idx = i
    if start_idx != -1 and 'st.divider()' in line and i > start_idx + 150:
        end_idx = i
        break

if start_idx == -1 or end_idx == -1:
    print('Failed to find Section 0')
    sys.exit(1)

print(f'Section 0 found from line {start_idx+1} to {end_idx+1}')
section_0_lines = lines[start_idx:end_idx+1]

del lines[start_idx:end_idx+1]

insert_idx = -1
for i, line in enumerate(lines):
    if '# --- SECTION 1C: GLOBAL MARKET FLOW' in line:
        insert_idx = i - 1
        if 'st.divider()' in lines[insert_idx]:
            insert_idx = insert_idx
        break

if insert_idx == -1:
    print('Failed to find insertion point')
    sys.exit(1)

print(f'Inserting at index {insert_idx}')
lines = lines[:insert_idx] + ['\n'] + section_0_lines + ['\n'] + lines[insert_idx:]

with open('dashboard_pro.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)

print('Success')

import sys
sys.stdout.reconfigure(encoding='utf-8')

path = r'web/templates/web/product-detail.html'

with open(path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

content = ''.join(lines)
original_len = len(content)

# ── Find the exact delivery col start/end by line numbers ──────────────────
# From find_lines.py: pdp-delivery-col starts at line 2316, 
# ends at line 2440 (</div>), then pdp-main-row closes at 2442, pdp-main-card at 2443

# We'll do line-based surgery
start_line = None  # 0-indexed line where <div class="pdp-delivery-col"> appears
end_line = None    # 0-indexed line of the closing </div> of pdp-delivery-col

for i, line in enumerate(lines):
    if '<div class="pdp-delivery-col">' in line and start_line is None:
        start_line = i
    if start_line is not None and i > start_line:
        # The closing </div> of pdp-delivery-col is followed by a blank line then </div> (pdp-main-row) then </div> (pdp-main-card)
        # From file: line 2440 has </div> closing pdp-delivery-col (0-indexed: 2439)
        if '</div>' in line.strip() and end_line is None:
            # Count depth to find our closing tag
            pass

print(f"pdp-delivery-col start (0-indexed): {start_line}")
print(f"Line content: {repr(lines[start_line][:80]) if start_line else 'NOT FOUND'}")

# Manual approach: use line numbers from find_lines.py (1-indexed)
# Line 2316 = index 2315 = start of pdp-delivery-col
# Line 2440 = index 2439 = closing </div> of pdp-delivery-col
DEL_START = 2315  # 0-indexed
DEL_END = 2440    # 0-indexed (exclusive, so up to but not including line 2440)

# Verify
print(f"Lines {DEL_START} to {DEL_END-1}:")
print(repr(lines[DEL_START][:80]))
print(repr(lines[DEL_END-1][:80]))
print(repr(lines[DEL_END][:80]))  # should be blank or pdp-main-row close

# Info strip to insert
INFO_STRIP = '''\t\t\t\t\t\t<!-- Delivery & Trust Strip -->
\t\t\t\t\t\t<div class="pdp-info-strip">
\t\t\t\t\t\t\t<div class="pdp-strip-item">
\t\t\t\t\t\t\t\t<i class="klb-icon-map-pin"></i>
\t\t\t\t\t\t\t\t<span>Whole United Kingdom</span>
\t\t\t\t\t\t\t</div>
\t\t\t\t\t\t\t<div class="pdp-strip-divider"></div>
\t\t\t\t\t\t\t<div class="pdp-strip-item">
\t\t\t\t\t\t\t\t<i class="klb-icon-truck"></i>
\t\t\t\t\t\t\t\t<span>Standard Delivery &mdash; 2&ndash;4 days</span>
\t\t\t\t\t\t\t</div>
\t\t\t\t\t\t\t<div class="pdp-strip-divider"></div>
\t\t\t\t\t\t\t<div class="pdp-strip-item">
\t\t\t\t\t\t\t\t<i class="klb-icon-credit-card"></i>
\t\t\t\t\t\t\t\t<span>Secure Stripe card payment</span>
\t\t\t\t\t\t\t</div>
\t\t\t\t\t\t\t<div class="pdp-strip-divider"></div>
\t\t\t\t\t\t\t<div class="pdp-strip-item">
\t\t\t\t\t\t\t\t<i class="klb-icon-refresh-cw"></i>
\t\t\t\t\t\t\t\t<span>Return requests available</span>
\t\t\t\t\t\t\t</div>
\t\t\t\t\t\t\t<div class="pdp-strip-divider"></div>
\t\t\t\t\t\t\t<div class="pdp-strip-item">
\t\t\t\t\t\t\t\t<i class="klb-icon-shield-check"></i>
\t\t\t\t\t\t\t\t<span>100% Authentic Quality</span>
\t\t\t\t\t\t\t</div>
\t\t\t\t\t\t</div>
'''

# Remove lines DEL_START to DEL_END (inclusive of closing blank line at 2440 = index 2439+1)
# Lines 2316..2440 (1-indexed) = 2315..2439 (0-indexed) = 125 lines
# But we keep line 2441 (index 2440) which is blank, and 2442 closes pdp-main-row, 2443 closes pdp-main-card

# After removal, insert INFO_STRIP after the pdp-main-card closing </div>
# pdp-main-row close: currently line 2442 (index 2441)
# pdp-main-card close: currently line 2443 (index 2442)
# After removing 125 lines (2315-2439), those become:
#   2441-125 = 2316 -> index 2315... wait let me just do it properly

new_lines = lines[:DEL_START]  # before pdp-delivery-col
new_lines += lines[DEL_END:]   # after pdp-delivery-col closing </div>

print(f"\nAfter removal: {len(new_lines)} lines (was {len(lines)})")
print(f"Line at old DEL_END (now start of continuation):")
for j in range(min(5, len(new_lines) - DEL_START)):
    print(f"  [{DEL_START+j}]: {repr(new_lines[DEL_START+j][:80])}")

# Now find where pdp-main-card closes (should be within first few lines after DEL_START)
# We need to insert strip after pdp-main-card closes
# Looking for: \t\t\t\t\t\t</div> followed by \t\t\t\t\t\t{% if product.is_package %}
insert_at = None
for i in range(DEL_START, min(DEL_START + 20, len(new_lines))):
    line = new_lines[i]
    if '{% if product.is_package %}' in line:
        # Insert strip at this index (before this line)
        insert_at = i
        break

if insert_at is None:
    # Fallback: find pdp-package-items-section
    for i in range(DEL_START, len(new_lines)):
        if 'pdp-package-items-section' in new_lines[i] or 'pdp-section-card' in new_lines[i]:
            insert_at = i
            break

print(f"\nWill insert strip at line index: {insert_at}")
if insert_at:
    print(f"  Before: {repr(new_lines[insert_at][:80])}")

if insert_at:
    new_lines = new_lines[:insert_at] + [INFO_STRIP] + new_lines[insert_at:]
    print("Strip inserted")

new_content = ''.join(new_lines)
with open(path, 'w', encoding='utf-8') as f:
    f.write(new_content)
print(f"Done. Was {original_len} chars, now {len(new_content)} chars")

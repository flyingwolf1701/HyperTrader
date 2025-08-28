"""
Quick script to fix all position_fragment_usd attribute errors
"""

import os
import re

def fix_file(filepath):
    """Fix attribute references in a file"""
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original = content
    
    # Replace position_fragment_usd with position_fragment['usd']
    content = re.sub(
        r'state\.position_fragment_usd',
        r"state.position_fragment['usd']",
        content
    )
    
    # Replace position_fragment_eth with position_fragment['coin_value']
    content = re.sub(
        r'state\.position_fragment_eth',
        r"state.position_fragment['coin_value']",
        content
    )
    
    # Special case for assignments that were setting to Decimal("0")
    content = re.sub(
        r"state\.position_fragment\['usd'\] = Decimal\([\"']0[\"']\)",
        r"state.position_fragment['usd'] = Decimal('0')",
        content
    )
    
    content = re.sub(
        r"state\.position_fragment\['coin_value'\] = Decimal\([\"']0[\"']\)",
        r"state.position_fragment['coin_value'] = Decimal('0')",
        content
    )
    
    if content != original:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    return False

def main():
    target_file = r"C:\Users\trini\Desktop\software_engineer\2025\crypto\HyperTrader\backend\src\strategy\strategy_manager.py"
    
    print(f"Fixing attribute references in: {target_file}")
    
    if os.path.exists(target_file):
        if fix_file(target_file):
            print("✅ File fixed successfully!")
        else:
            print("No changes needed")
    else:
        print(f"❌ File not found: {target_file}")

if __name__ == "__main__":
    main()
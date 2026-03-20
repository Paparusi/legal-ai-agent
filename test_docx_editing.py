#!/usr/bin/env python3
"""
Test DOCX editing functionality
"""
from pathlib import Path
import sys
sys.path.insert(0, 'src')

from services.docx_editor import create_docx_from_text, edit_docx_file, extract_text_from_docx

def test_docx_editing():
    print("📝 Testing DOCX editing...")
    
    # Create test directory
    test_dir = Path("test_output")
    test_dir.mkdir(exist_ok=True)
    
    # 1. Create a simple DOCX
    print("\n1. Creating test DOCX...")
    test_text = """HỢP ĐỒNG LÀM VIỆC

ĐIỀU 1: Các bên tham gia
Bên A: Công ty ABC
Bên B: Nguyễn Văn A

ĐIỀU 2: Mức lương
Mức lương: 10.000.000 VNĐ/tháng

ĐIỀU 3: Thời hạn hợp đồng
Thời hạn: 12 tháng kể từ ngày ký
"""
    
    input_file = test_dir / "test_contract.docx"
    create_docx_from_text(test_text, str(input_file), title="Hợp đồng Test")
    print(f"   ✓ Created: {input_file}")
    
    # 2. Edit the DOCX
    print("\n2. Applying edits...")
    edits = [
        {"find": "10.000.000 VNĐ", "replace": "15.000.000 VNĐ"},
        {"find": "12 tháng", "replace": "24 tháng"},
        {"find": "Nguyễn Văn A", "replace": "Nguyễn Văn B"}
    ]
    
    output_file = test_dir / "test_contract_edited.docx"
    result = edit_docx_file(str(input_file), str(output_file), edits)
    
    print(f"   ✓ Edited: {output_file}")
    print(f"   ✓ Changes made: {result['changes_made']}")
    print(f"   ✓ Edits applied: {len(result['edits_applied'])}")
    
    # 3. Verify edits
    print("\n3. Verifying edits...")
    original_text = extract_text_from_docx(str(input_file))
    edited_text = extract_text_from_docx(str(output_file))
    
    print(f"   Original length: {len(original_text)} chars")
    print(f"   Edited length: {len(edited_text)} chars")
    
    # Check if edits were applied
    assert "15.000.000 VNĐ" in edited_text, "Salary edit not found"
    assert "24 tháng" in edited_text, "Duration edit not found"
    assert "Nguyễn Văn B" in edited_text, "Name edit not found"
    
    print("\n✅ All tests passed!")
    print(f"\nTest files created in: {test_dir.absolute()}")
    return True

if __name__ == "__main__":
    try:
        test_docx_editing()
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

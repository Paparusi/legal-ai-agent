"""Test LibreOffice editor integration"""
from src.services.libreoffice_editor import find_libreoffice, edit_docx, convert_to_pdf
import os

print("Testing LibreOffice integration...\n")

print("1. Checking LibreOffice availability...")
soffice = find_libreoffice()
if soffice:
    print(f"   ✓ LibreOffice found: {soffice}")
else:
    print("   ⚠ LibreOffice NOT found (will use python-docx fallback)")

print("\n2. Testing DOCX editing...")
# Check if test file exists
test_input = "test_output/test_input.docx"
if os.path.exists(test_input):
    test_output = "test_output/test_edited_output.docx"
    
    edits = [
        {"find": "old text", "replace": "new text"},
        {"find": "example", "replace": "EXAMPLE"}
    ]
    
    try:
        result = edit_docx(test_input, test_output, edits)
        print(f"   ✓ Edit successful!")
        print(f"     - Changes: {result['changes_made']}")
        print(f"     - Method: {result.get('method', 'unknown')}")
        print(f"     - Output: {result['output_path']}")
        
        if soffice and os.path.exists(test_output):
            print("\n3. Testing PDF conversion...")
            try:
                pdf_path = convert_to_pdf(test_output)
                print(f"   ✓ PDF created: {pdf_path}")
                print(f"   ✓ PDF exists: {os.path.exists(pdf_path)}")
            except Exception as e:
                print(f"   ✗ PDF conversion failed: {e}")
    
    except Exception as e:
        print(f"   ✗ Edit failed: {e}")
else:
    print(f"   ⚠ Test file not found: {test_input}")
    print("   Skipping DOCX edit test")

print("\n✅ LibreOffice tests complete!")

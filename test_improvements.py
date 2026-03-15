#!/usr/bin/env python3
"""
Test script for Legal AI Agent improvements
Tests search query extraction, domain detection, and multi-query search
"""
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from api.main import extract_search_query, detect_domain, multi_query_search

def test_search_extraction():
    """Test search query extraction"""
    print("=" * 60)
    print("TEST 1: Search Query Extraction")
    print("=" * 60)
    
    test_cases = [
        "Thời gian thử việc tối đa là bao lâu?",
        "Nghỉ phép năm được bao nhiêu ngày?",
        "Thuế suất thuế TNDN hiện hành là bao nhiêu?",
        "Hợp đồng lao động phải có những điều khoản gì?",
        "Thành lập công ty cổ phần cần thủ tục thế nào?"
    ]
    
    for question in test_cases:
        extracted = extract_search_query(question)
        print(f"\nCâu hỏi: {question}")
        print(f"Trích xuất: {extracted}")

def test_domain_detection():
    """Test domain auto-detection"""
    print("\n" + "=" * 60)
    print("TEST 2: Domain Auto-Detection")
    print("=" * 60)
    
    test_cases = [
        "Thời gian thử việc tối đa là bao lâu?",
        "Thuế suất thuế TNDN hiện hành là bao nhiêu?",
        "Nghỉ phép năm được bao nhiêu ngày?",
        "Thành lập công ty cổ phần cần bao nhiêu vốn?",
        "Quyền sử dụng đất được chuyển nhượng như thế nào?"
    ]
    
    for question in test_cases:
        domains = detect_domain(question)
        print(f"\nCâu hỏi: {question}")
        print(f"Lĩnh vực phát hiện: {domains or 'Không xác định'}")

def test_multi_search():
    """Test multi-query search"""
    print("\n" + "=" * 60)
    print("TEST 3: Multi-Query Search")
    print("=" * 60)
    
    test_cases = [
        ("Thời gian thử việc tối đa là bao lâu?", ["lao_dong"]),
        ("Thuế suất thuế TNDN hiện hành là bao nhiêu?", ["thue"]),
        ("Nghỉ phép năm được bao nhiêu ngày?", ["lao_dong"])
    ]
    
    for question, domains in test_cases:
        print(f"\n{'=' * 50}")
        print(f"Câu hỏi: {question}")
        print(f"Lĩnh vực: {domains}")
        
        try:
            results = multi_query_search(question, domains, limit=5)
            print(f"Kết quả: {len(results)} nguồn luật")
            
            for i, result in enumerate(results[:3], 1):
                print(f"\n  [{i}] {result['law_title']}")
                print(f"      Điều: {result.get('article', 'N/A')}")
                print(f"      Số: {result.get('law_number', 'N/A')}")
                print(f"      Độ liên quan: {result.get('rank', 0):.4f}")
                print(f"      Nội dung: {result['content'][:100]}...")
        except Exception as e:
            print(f"  ❌ Lỗi: {e}")

def main():
    print("\n🧪 TESTING LEGAL AI AGENT IMPROVEMENTS")
    print("=" * 60)
    
    # Test 1: Search extraction
    test_search_extraction()
    
    # Test 2: Domain detection
    test_domain_detection()
    
    # Test 3: Multi-query search (requires DB connection)
    print("\n" + "=" * 60)
    print("⚠️  Test 3 requires database connection")
    print("=" * 60)
    
    try:
        test_multi_search()
    except Exception as e:
        print(f"\n❌ Cannot test multi-search (DB not available): {e}")
    
    print("\n" + "=" * 60)
    print("✅ Tests completed!")
    print("=" * 60)

if __name__ == "__main__":
    main()

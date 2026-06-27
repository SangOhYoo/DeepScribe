"""Quick test for novel_translator modules."""
import sys
sys.path.insert(0, "D:\\DeepScribe")

from novel_translator.services.chunker import SmartChunker
from novel_translator.services.glossary import GlossaryManager

# Test SmartChunker
c = SmartChunker(context_size=16384, source_lang="ja")
print(f"max_input_tokens: {c.max_input_tokens}")
print(f"max_chars: {c.max_chars}")

# Test with sample text
para1 = "彼女は窓の外を見つめていた。風が強く吹いている。" * 30
para2 = "「こんにちは」と彼は言った。" * 30
para3 = "夕日が美しく沈んでいく。空は赤く染まっていた。" * 30
sample = f"第一章\n\n{para1}\n\n{para2}\n\n{para3}"

chunks = c.chunk_text(sample)
print(f"\nSample: {len(sample)} chars -> {len(chunks)} chunks")
for i, ch in enumerate(chunks):
    print(f"  Chunk {i}: ~{ch.estimated_tokens} tokens, {len(ch.text)} chars")

# Test GlossaryManager
g = GlossaryManager()
g.add_entry("田中", "타나카", "character")
g.add_entry("東京", "도쿄", "location")
print(f"\nGlossary: {g.size} entries")
print(g.format_for_prompt("田中は東京に行った"))

# Test PostProcessor Repetition Collapsing
from novel_translator.services.postprocessor import PostProcessor

pp = PostProcessor()
test_repeat_text = (
    "“아아아아아아아아아아아아아아아아아아아아아아아아아아아아아아아아아아아아아아아아아아악\n"
    "~ ~ !?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!\n"
    "!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!\n"
    "!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!?!"
)
cleaned = pp.clean_repetitions(test_repeat_text)
print("\n--- Repetition Collapse Test ---")
print("Original text snippet:\n" + test_repeat_text[:120] + "...")
print("Cleaned text snippet:\n" + cleaned)
print("--------------------------------")

assert "아아아아아아아아아" not in cleaned, "Scream was not collapsed!"
assert cleaned.count("!?!?!?!?") <= 5, "Punctuation loop was not collapsed!"

# Test Name Unification
test_name_text = (
    "“히토미(仁美) 씨, 바스타올로 앞은 가리고 있었지만, 너무 당황해서 가슴 골이 선명하게 보여 버려서…”\n"
    "“그럴 거예요. 당황하게 해서 히토미(仁美) 씨에게는 죄송했지만, 저는 엄청 두근거렸거든요. 히토미(仁美) 씨의 가슴이 그렇게 클 줄은 몰랐습니다.”\n"
    "“저는 더 이상 봐서는 안 된다고 생각해서 거실에 가서 기다렸어요. 잠시 후, 마유미(仁美) 씨가 옷을 가져다주었습니다.”\n"
    "“마유미(仁美) 씨가 갈아입고 나왔는데… 노브라였어요. 하얀 티셔츠 한 장뿐이었고, 하반신까지 푹 가려지는 커다란 셔츠였지만, 가슴 부근에 볼록하게…”"
)
unified = pp.unify_names(test_name_text)
print("\n--- Name Unification Test ---")
print("Original text:")
print(test_name_text)
print("\nUnified text:")
print(unified)
print("------------------------------")

assert "마유미(仁美)" not in unified, "Parenthesized name was not unified!"
assert "마유미" not in unified, "Standalone name was not unified!"
assert "히토미(仁美)" in unified, "Target name was lost!"

print("\n=== ALL TESTS PASSED ===")


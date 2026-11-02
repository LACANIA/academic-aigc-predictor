# DOCX input contract · RC1-DOCX

Read-only ZIP/OOXML traversal provides title, common/styled headings, abstract, keywords, narrative, equations, structured table rows/cells, captions, appendix, statements, references and a distinct biography region. Source paragraph indices include empty paragraphs and table-cell paragraphs; they do not equal Word page numbers.

Normalized paragraph text is the exact-quote target. Raw paragraph XML, original document.xml bytes and OMML XML are private evidence. Fractions, exponents, roots and matrices receive structural reading hints separately, without mathematical equivalence certification. No OCR/rendering means image-only text, embedded equations and diagram content can remain unreadable.

The static reader never invokes Word, follows a relationship or extracts ZIP members to disk. It rejects macro packages, DTD/entity declarations, unsafe paths, duplicate member names, encryption, unsupported compression, symbolic links, oversized resources and excessive expansion/nesting. Limits are engineering bounds. Tracked deletions are omitted from visible text, insertions included, with warnings. Alternate imported content and unsupported containers retain warnings and original XML without guessed prose.

Each block retains source_type=docx_ooxml, source hash, file, part, block ID, paragraph index, section, original/normalized text and warnings. Table coordinates use row/column, grid span and vertical-merge indicators, not rendered geometry. Floating objects and note placement can differ from visible reading order; disclose gaps.


Portable calls use the bundled scripts/precheck.py and explicit --knowledge. No development-repository fallback.

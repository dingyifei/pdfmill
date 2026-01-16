"""Tests for pdfmill.selector module."""

import pytest

from pdfmill.selector import (
    PageSelectionError,
    _select_from_list,
    select_pages,
    validate_page_spec_syntax,
)


class TestSelectPagesKeywords:
    """Test keyword-based page selection."""

    def test_first_page(self):
        assert select_pages("first", 5) == [0]

    def test_first_page_single_page_doc(self):
        assert select_pages("first", 1) == [0]

    def test_last_page(self):
        assert select_pages("last", 5) == [4]

    def test_last_page_single_page_doc(self):
        assert select_pages("last", 1) == [0]

    def test_all_pages(self):
        assert select_pages("all", 3) == [0, 1, 2]

    def test_all_pages_single_page(self):
        assert select_pages("all", 1) == [0]

    def test_odd_pages(self):
        # Pages 1, 3, 5 (1-indexed) -> indices 0, 2, 4
        assert select_pages("odd", 6) == [0, 2, 4]

    def test_odd_pages_single_page(self):
        assert select_pages("odd", 1) == [0]

    def test_even_pages(self):
        # Pages 2, 4, 6 (1-indexed) -> indices 1, 3, 5
        assert select_pages("even", 6) == [1, 3, 5]

    def test_even_pages_single_page(self):
        # No even pages in 1-page doc
        assert select_pages("even", 1) == []

    def test_case_insensitive_first(self):
        assert select_pages("FIRST", 5) == [0]

    def test_case_insensitive_last(self):
        assert select_pages("Last", 5) == [4]

    def test_whitespace_trimmed(self):
        assert select_pages("  first  ", 5) == [0]


class TestSelectPagesRanges:
    """Test range-based page selection."""

    def test_simple_range(self):
        # "1-3" -> pages 1, 2, 3 -> indices 0, 1, 2
        assert select_pages("1-3", 5) == [0, 1, 2]

    def test_open_end_range(self):
        # "3-" -> page 3 to end -> indices 2, 3, 4
        assert select_pages("3-", 5) == [2, 3, 4]

    def test_last_n_pages(self):
        # "-2" -> last 2 pages -> indices 3, 4
        assert select_pages("-2", 5) == [3, 4]

    def test_last_n_pages_equals_total(self):
        assert select_pages("-5", 5) == [0, 1, 2, 3, 4]

    def test_range_with_negative_offset(self):
        # "1--1" -> page 1 to second-to-last -> indices 0, 1, 2, 3
        assert select_pages("1--1", 5) == [0, 1, 2, 3]

    def test_range_with_negative_offset_from_middle(self):
        # "2--1" -> page 2 to second-to-last -> indices 1, 2, 3
        assert select_pages("2--1", 5) == [1, 2, 3]

    def test_range_exceeds_total_pages(self):
        # "1-10" on 5-page doc should cap at 5
        assert select_pages("1-10", 5) == [0, 1, 2, 3, 4]

    def test_single_page_range(self):
        # "2-2" -> just page 2 -> index 1
        assert select_pages("2-2", 5) == [1]


class TestSelectPagesLists:
    """Test list-based page selection."""

    def test_list_input(self):
        # [1, 3, 5] -> indices 0, 2, 4
        assert select_pages([1, 3, 5], 5) == [0, 2, 4]

    def test_list_single_item(self):
        assert select_pages([3], 5) == [2]

    def test_negative_index_in_list(self):
        # [-1] -> last page -> index 4
        assert select_pages([-1], 5) == [4]

    def test_negative_indices_multiple(self):
        # [-1, -2] -> last and second-to-last -> indices 4, 3
        assert select_pages([-1, -2], 5) == [4, 3]

    def test_mixed_positive_and_negative(self):
        # [1, -1] -> first and last -> indices 0, 4
        assert select_pages([1, -1], 5) == [0, 4]


class TestSelectPagesSinglePage:
    """Test single page number selection."""

    def test_single_page_string(self):
        # "2" -> page 2 -> index 1
        assert select_pages("2", 5) == [1]

    def test_single_page_int(self):
        # Integer input
        assert select_pages(2, 5) == [1]

    def test_first_page_number(self):
        assert select_pages("1", 5) == [0]

    def test_last_page_number(self):
        assert select_pages("5", 5) == [4]


class TestSelectPagesErrors:
    """Test error cases."""

    def test_no_pages_raises(self):
        with pytest.raises(PageSelectionError, match="no pages"):
            select_pages("first", 0)

    def test_invalid_spec_raises(self):
        with pytest.raises(PageSelectionError, match="Unknown"):
            select_pages("invalid", 5)

    def test_page_out_of_range_raises(self):
        with pytest.raises(PageSelectionError, match="out of range"):
            select_pages("10", 5)

    def test_negative_too_large_raises(self):
        with pytest.raises(PageSelectionError, match="Cannot select"):
            select_pages("-10", 5)

    def test_invalid_range_format_raises(self):
        with pytest.raises(PageSelectionError, match="Invalid range"):
            select_pages("1-2-3", 5)

    def test_start_after_end_raises(self):
        with pytest.raises(PageSelectionError, match="after end"):
            select_pages("5-3", 5)

    def test_list_page_out_of_range(self):
        with pytest.raises(PageSelectionError, match="out of range"):
            select_pages([10], 5)

    def test_list_negative_too_large(self):
        with pytest.raises(PageSelectionError, match="out of range"):
            select_pages([-10], 5)


class TestSelectFromList:
    """Test the _select_from_list helper function."""

    def test_positive_indices(self):
        # 1-indexed to 0-indexed
        assert _select_from_list([1, 2, 3], 5) == [0, 1, 2]

    def test_negative_indices(self):
        # -1 -> last, -2 -> second to last
        assert _select_from_list([-1, -2], 5) == [4, 3]

    def test_mixed_indices(self):
        assert _select_from_list([1, -1], 5) == [0, 4]

    def test_out_of_range_positive(self):
        with pytest.raises(PageSelectionError):
            _select_from_list([10], 5)

    def test_out_of_range_negative(self):
        with pytest.raises(PageSelectionError):
            _select_from_list([-10], 5)


class TestValidatePageSpecSyntax:
    """Test page spec syntax validation without total_pages."""

    # Valid keyword cases
    def test_keyword_first(self):
        validate_page_spec_syntax("first")  # Should not raise

    def test_keyword_last(self):
        validate_page_spec_syntax("last")

    def test_keyword_all(self):
        validate_page_spec_syntax("all")

    def test_keyword_odd(self):
        validate_page_spec_syntax("odd")

    def test_keyword_even(self):
        validate_page_spec_syntax("even")

    def test_keyword_case_insensitive(self):
        validate_page_spec_syntax("LAST")
        validate_page_spec_syntax("All")
        validate_page_spec_syntax("FIRST")

    def test_keyword_with_whitespace(self):
        validate_page_spec_syntax("  first  ")

    # Valid list cases
    def test_integer_list(self):
        validate_page_spec_syntax([1, 3, 5])

    def test_negative_in_list(self):
        validate_page_spec_syntax([-1, -2])

    def test_mixed_list(self):
        validate_page_spec_syntax([1, -1, 3])

    def test_empty_list(self):
        validate_page_spec_syntax([])

    # Valid single int cases
    def test_single_int(self):
        validate_page_spec_syntax(5)

    def test_single_int_string(self):
        validate_page_spec_syntax("5")

    def test_large_page_number(self):
        # Large numbers are valid syntax (runtime check catches out-of-range)
        validate_page_spec_syntax("999999")

    # Valid range cases
    def test_simple_range(self):
        validate_page_spec_syntax("1-3")

    def test_open_end_range(self):
        validate_page_spec_syntax("3-")

    def test_last_n_pages(self):
        validate_page_spec_syntax("-2")

    def test_negative_offset_range(self):
        validate_page_spec_syntax("1--1")

    def test_negative_offset_range_open_start(self):
        validate_page_spec_syntax("--1")

    # Invalid cases
    def test_unknown_keyword_raises(self):
        with pytest.raises(PageSelectionError, match="Unknown"):
            validate_page_spec_syntax("abc")

    def test_unknown_keyword_typo_raises(self):
        with pytest.raises(PageSelectionError, match="Unknown"):
            validate_page_spec_syntax("frist")

    def test_too_many_hyphens_raises(self):
        with pytest.raises(PageSelectionError, match="hyphens"):
            validate_page_spec_syntax("1-2-3")

    def test_non_integer_in_range_raises(self):
        with pytest.raises(PageSelectionError, match="must be integers"):
            validate_page_spec_syntax("a-b")

    def test_non_integer_start_raises(self):
        with pytest.raises(PageSelectionError, match="must be integers"):
            validate_page_spec_syntax("a-3")

    def test_non_integer_end_raises(self):
        with pytest.raises(PageSelectionError, match="must be integers"):
            validate_page_spec_syntax("1-b")

    def test_mixed_type_list_raises(self):
        with pytest.raises(PageSelectionError, match="only integers"):
            validate_page_spec_syntax([1, "2", 3])

    def test_string_in_list_raises(self):
        with pytest.raises(PageSelectionError, match="only integers"):
            validate_page_spec_syntax(["first"])

    def test_float_in_list_raises(self):
        with pytest.raises(PageSelectionError, match="only integers"):
            validate_page_spec_syntax([1.5])

    def test_empty_string_raises(self):
        with pytest.raises(PageSelectionError, match="cannot be empty"):
            validate_page_spec_syntax("")

    def test_whitespace_only_raises(self):
        with pytest.raises(PageSelectionError, match="cannot be empty"):
            validate_page_spec_syntax("   ")

    def test_invalid_negative_offset_raises(self):
        with pytest.raises(PageSelectionError, match="must be integers"):
            validate_page_spec_syntax("1--a")

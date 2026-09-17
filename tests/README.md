# Tests

This file lists all tests in the suite, organised by source format.

## CSV

- `1-base`: default options. The header row is read as data, and each row is a container of positional slots holding plain literals.
- `2-headers`: `csv.headers=true`. The header row names the slots, and each row is a container of `xyz:` properties.
- `3-features`: `csv.headers=true` on a file that uses many CSV features:
  - quoted fields containing commas, escaped quotes and line breaks;
  - quoted and unquoted empty fields, and a whitespace-only field;
  - leading and trailing spaces;
  - number-like strings;
  - non-ASCII characters.
- `4-tsv`: default options on a `.tsv` file. The delimiter defaults to tab, so a comma inside a field doesn't split it.
- `5-tab`: default options on a `.tab` file. Same as `4-tsv`.

## JSON

- `1-base`: default options on a flat object with a string and a number. Keys become `xyz:` properties of the root.
- `2-features`: default options on an object covering all JSON value types:
  - strings with escape sequences and Unicode;
  - integer, negative, zero, `-0`, decimal, exponent and big-integer numbers;
  - booleans and `null`;
  - empty and nested objects and arrays, including an array with mixed types;
  - keys with spaces, an empty key and a non-ASCII key.

## XML

- `1-base`: default options on a single element with an attribute and a child element. Element names become types, attributes become properties, and children become numbered slots.
- `2-features`: default options on a document covering many XML features:
  - prolog, `DOCTYPE`, comments and processing instructions;
  - default and prefixed namespaces, and namespaced attributes;
  - predefined entities, character references and CDATA;
  - mixed content, `xml:space` and `xml:lang`;
  - empty and whitespace-only elements;
  - Unicode and deep nesting.

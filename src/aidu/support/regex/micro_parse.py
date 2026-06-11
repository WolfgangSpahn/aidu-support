# Copyright (c) 2026 Wolfgang Spahn, PHBern
# Licensed under the MIT License.
# Please follow standard academic practice when using this software in research or publications.
# See LICENSE for the full text.

"""
This module provides a utility function to compile a template string with placeholders into a regex pattern.
Placeholders are denoted by {name} and will be converted into named regex groups.
For example, the template "p:{protons},n:{neutrons},e:{electrons} | " will be converted into a regex that 
can extract the values of protons, neutrons, and electrons from a string like "p:1,n:0,e:1 | This is hydrogen".
"""

import re


def compile_prompt_parser(template: str):
    """
    Compiles a template string with placeholders into a regex pattern.
    """

    pattern = re.escape(template)

    pattern = re.sub(
        r"\\\{(\w+)\\\}",
        r"(?P<\1>.*?)",
        pattern,
    )

    pattern += r"(?P<text>.*)$"

    return re.compile(pattern)


def smoke_test():
    data_prompt = "p:{protons},n:{neutrons},e:{electrons} | "
    parser = compile_prompt_parser(data_prompt)

    test_string = "p:1,n:0,e:1 | This is hydrogen"

    match = parser.match(test_string)
    if match:
        print("Protons:", match.group("protons"))
        print("Neutrons:", match.group("neutrons"))
        print("Electrons:", match.group("electrons"))
        print("Text:", match.group("text"))
    else:
        print("No match found.")


if __name__ == "__main__":
    smoke_test()
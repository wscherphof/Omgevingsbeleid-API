# SPDX-License-Identifier: EUPL-1.2
# Copyright (C) 2018 - 2020 Provincie Zuid-Holland

"""
Tests that perform checks on comparison functions.
"""

import os
import pytest
import Endpoints.comparison
import marshmallow as MM

def test_simple_list():
    old_list = [1,2,3]
    new_list = [1,4,5,6]
    assert Endpoints.comparison.diff_lists(old_list, new_list) == {
        'new':[4,5,6],
        'removed':[2,3],
        'same':[1]
    }

def test_empty_list():
    old_list = [1,2,3]
    new_list = []
    assert Endpoints.comparison.diff_lists(old_list, new_list) == {
        'new':[],
        'removed':[1,2,3],
        'same':[]
    }

def test_text():
    old_text = '''Oh, well, I'd like to buy a copy of an 'Illustrated History of False Teeth'.'''
    new_text = '''Oh, well, I'd like to buy 'Illustrated History of False Teeth' do you have that.'''
    change_text = '''Oh, well, I'd like to buy <div class='revision-removal'>a copy of an </div>'Illustrated History of False Teeth'<div class='revision-insert'> do you have that</div>.'''
    assert Endpoints.comparison.diff_text_toHTML(old_text, new_text) == change_text

def test_mapping():
    class SimpleMapping(MM.Schema):
        name = MM.fields.String(allow_none=True)

    old_mapping = SimpleMapping().load({'name':'John Doe'})
    new_mapping = SimpleMapping().load({'name':'Jane Doe'})
    change_mapping = {'name':"J<div class='revision-removal'>ohn</div><div class='revision-insert'>ane</div> Doe"}
    assert Endpoints.comparison.compare_objects(SimpleMapping(), old_mapping, new_mapping) == change_mapping

def test_empty_field():
    class SimpleMapping(MM.Schema):
        name = MM.fields.String(allow_none=True)

    old_mapping = SimpleMapping().load({'name':'John Doe'})
    new_mapping = SimpleMapping().load({'name':None})
    change_mapping = {'name':"<div class='revision-removal'>John Doe</div>"}
    assert Endpoints.comparison.compare_objects(SimpleMapping(), old_mapping, new_mapping) == change_mapping
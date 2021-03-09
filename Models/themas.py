# SPDX-License-Identifier: EUPL-1.2
# Copyright (C) 2018 - 2020 Provincie Zuid-Holland

import marshmallow as MM
from Endpoints.endpoint import Base_Schema


class Themas_Schema(Base_Schema):
    Titel = MM.fields.Str(required=True, obprops=['search_title'])
    Omschrijving = MM.fields.Str(missing=None, obprops=['search_description'])
    Weblink = MM.fields.Str(missing=None, obprops=[])

    class Meta(Base_Schema.Meta):
        slug = 'themas'
        table = 'Themas'
        read_only = False
        ordered = True
        searchable = True
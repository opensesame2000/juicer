# -*- coding: utf-8 -*-
# Juicer - Administer Pulp and Release Carts
# Copyright © 2012, Red Hat, Inc.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

######################################################################
# PULP RETURN CODES
######################################################################
#
# For a full list of return codes with complete descriptions see the
# official pulp documentation:
# https://fedorahosted.org/pulp/wiki/RestApiDevelopment#HTTPResponses
#
######################################################################
# GET
PULP_GET_OK = 200
PULP_GET_BAD_REQUEST = 400
PULP_GET_NOT_FOUND = 404

######################################################################
# POST
PULP_POST_OK = 200
PULP_POST_CREATED = 201
PULP_POST_ACCEPTED = 202
PULP_POST_NO_CONTENT = 204
PULP_POST_BAD_REQUEST = 400
PULP_POST_NOT_FOUND = 404
PULP_POST_CONFLICT = 409

######################################################################
# PUT
PULP_PUT_OK = 200
PULP_PUT_BAD_REQUEST = 400
PULP_PUT_NOT_FOUND = 404

######################################################################
# DELETE
PULP_DELETE_OK = 200
PULP_DELETE_ACCEPTED = 202
PULP_DELETE_NOT_FOUND = 404

######################################################################
# OPTIONS
PULP_OPTIONS_OK = 200

######################################################################
# MISC. MAGIC NUMBERS
######################################################################

######################################################################
# Amount of data to upload at a time
UPLOAD_AT_ONCE = 10485760

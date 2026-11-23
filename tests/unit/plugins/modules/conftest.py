# -*- coding: utf-8 -*-
# Copyright (c) NodeRings contributors
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import contextlib
import json

import pytest

try:
    from ansible.module_utils.testing import patch_module_args
except ImportError:  # ansible-core < 2.19
    patch_module_args = None

from ansible.module_utils import basic
from ansible.module_utils.common.text.converters import to_bytes

from ansible_collections.noderings.cloud.plugins.module_utils import noderings
from ansible_collections.noderings.cloud.tests.unit.plugins.modules.fakeapi import FakeAPI


class ExitJson(Exception):
    pass


class FailJson(Exception):
    pass


def _exit_json(self, **kwargs):
    kwargs.setdefault("changed", False)
    raise ExitJson(kwargs)


def _fail_json(self, **kwargs):
    kwargs["failed"] = True
    raise FailJson(kwargs)


@pytest.fixture
def api(monkeypatch):
    fake = FakeAPI()
    monkeypatch.setattr(noderings, "open_url", fake)
    monkeypatch.setattr(noderings.time, "sleep", lambda s: None)
    monkeypatch.setattr(basic.AnsibleModule, "exit_json", _exit_json)
    monkeypatch.setattr(basic.AnsibleModule, "fail_json", _fail_json)
    return fake


@pytest.fixture
def run(monkeypatch):
    """Run a module's main() with args; returns (result, failed)."""
    def _run(module, args, check_mode=False):
        args = dict(args)
        args.setdefault("api_token", "test-token")
        if check_mode:
            args["_ansible_check_mode"] = True
        if patch_module_args is not None:
            ctx = patch_module_args(args)
        else:
            monkeypatch.setattr(basic, "_ANSIBLE_ARGS", to_bytes(json.dumps({"ANSIBLE_MODULE_ARGS": args})))
            ctx = contextlib.nullcontext()
        with ctx:
            try:
                module.main()
            except ExitJson as e:
                return e.args[0]
            except FailJson as e:
                return e.args[0]
        raise AssertionError("module did not exit")
    return _run

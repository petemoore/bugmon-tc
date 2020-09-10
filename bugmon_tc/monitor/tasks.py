# -*- coding: utf-8 -*-

# This Source Code Form is subject to the terms of the Mozilla Public License,
# v. 2.0. If a copy of the MPL was not distributed with this file, You can
# obtain one at http://mozilla.org/MPL/2.0/.
from datetime import datetime, timedelta

from taskcluster.utils import fromNow
from taskcluster.utils import slugId
from taskcluster.utils import stringDate


class ProcessorTask(object):
    """
    Helper class for generating processor tasks
    """

    TASK_NAME = "Bugmon Processor Task"

    def __init__(self, parent_id, src, dest=None, deps=None):
        """

        :param parent_id: ID of parent task
        :param src: Path to monitor artifact
        :param dest: Path to artifact generated by task
        :param deps: Additional dependencies needed by the task
        """
        self.id = slugId()
        self.parent_id = parent_id
        self.src = src
        self.dest = dest

        self.deps = [parent_id]
        if deps is not None:
            self.deps.extend(deps)
        self.worker = "bugmon-processor"

    @property
    def env(self):
        """ Environment variables for the task """
        return {
            "BUGMON_ACTION": "PROCESS",
            "MONITOR_ARTIFACT": self.src,
            "PROCESSOR_ARTIFACT": self.dest,
        }

    @property
    def scopes(self):
        """ Scopes applied to the task """
        return [
            "docker-worker:capability:device:hostSharedMemory",
            "docker-worker:capability:device:loopbackAudio",
            "docker-worker:capability:privileged",
            "queue:scheduler-id:-",
            f"queue:get-artifact:project/fuzzing/bugmon/{self.src}",
        ]

    @property
    def task(self):
        """ Task definition """
        now = datetime.utcnow()

        return {
            "taskGroupId": self.parent_id,
            "dependencies": self.deps,
            "created": stringDate(now),
            "deadline": stringDate(now + timedelta(hours=2)),
            "expires": stringDate(fromNow("1 week", now)),
            "provisionerId": "proj-fuzzing",
            "metadata": {
                "description": "",
                "name": self.TASK_NAME,
                "owner": "fuzzing+taskcluster@mozilla.com",
                "source": "https://github.com/MozillaSecurity/bugmon",
            },
            "payload": {
                "artifacts": {
                    "project/fuzzing/bugmon": {
                        "path": "/bugmon-artifacts/",
                        "type": "directory",
                    }
                },
                "cache": {},
                "capabilities": {
                    "devices": {"hostSharedMemory": True, "loopbackAudio": True}
                },
                "env": self.env,
                "features": {"taskclusterProxy": True},
                "image": "mozillasecurity/bugmon:latest",
                "maxRunTime": 3600,
            },
            "priority": "high",
            "workerType": self.worker,
            "retries": 5,
            "routes": [],
            "schedulerId": "-",
            "scopes": self.scopes,
            "tags": {},
        }


class ReporterTask(ProcessorTask):
    """
    Helper class for generating reporter tasks
    """

    TASK_NAME = "Bugmon Reporter Task"

    def __init__(self, parent_id, src, dest=None, deps=None):
        super().__init__(parent_id, src, dest, deps)

        self.worker = "bugmon-monitor"

    @property
    def env(self):
        """ Environment variables for the task """
        return {
            "BUGMON_ACTION": "REPORT",
            "PROCESSOR_ARTIFACT": self.src,
        }

    @property
    def scopes(self):
        """ Scopes applied to the task """
        return [
            "queue:scheduler-id:-",
            f"queue:get-artifact:project/fuzzing/bugmon/{self.src}",
            "secrets:get:project/fuzzing/bz-api-key",
        ]

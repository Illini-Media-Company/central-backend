from apscheduler.schedulers.base import (
    BaseScheduler,
    STATE_PAUSED,
    STATE_RUNNING,
    STATE_STOPPED,
    Mapping,
    obj_to_ref,
    ExitStack,
    ref_to_obj,
    Job,
)
from db.json_store import json_store_get


def to_json(self, jobstore=None):
    """
    Export stored jobs as JSON.

    :param outfile: either a file object opened in text write mode ("w"), or a path
        to the target file
    :param jobstore: alias of the job store to export jobs from (if omitted, export
        from all configured job stores)

    """
    import json
    import pickle
    from base64 import b64encode

    from apscheduler import version

    if self.state == STATE_STOPPED:
        raise RuntimeError(
            "the scheduler must have been started for job export to work"
        )

    def encode_with_pickle(obj):
        return b64encode(pickle.dumps(obj, pickle.HIGHEST_PROTOCOL)).decode("ascii")

    def json_default(obj):
        if hasattr(obj, "__getstate__") and hasattr(obj, "__setstate__"):
            state = obj.__getstate__()
            if isinstance(state, Mapping):
                return {
                    "__apscheduler_class__": obj_to_ref(obj.__class__),
                    "__apscheduler_state__": state,
                }

        return {"__apscheduler_pickle__": encode_with_pickle(obj)}

    with self._jobstores_lock:
        all_jobs = [
            job
            for alias, store in self._jobstores.items()
            for job in store.get_all_jobs()
            if jobstore in (None, alias)
        ]

    to_return = ""

    with ExitStack() as stack:
        # if not hasattr(outfile, "write"):
        #     outfile = stack.enter_context(open(outfile, "w"))

        to_return = json.dumps(
            {
                "version": 1,
                "scheduler_version": version,
                "jobs": [job.__getstate__() for job in all_jobs],
            },
            default=json_default,
        )

    return to_return


def import_from_db(self, key, jobstore="default"):
    """
    Import jobs previously exported via :meth:`export_jobs.

    :param infile: either a file object opened in text read mode ("r") or a path to
        a JSON file containing previously exported jobs
    :param jobstore: the alias of the job store to import the jobs to

    """
    import json
    import pickle
    from base64 import b64decode

    def json_object_hook(dct):
        if pickle_data := dct.get("__apscheduler_pickle__"):
            return pickle.loads(b64decode(pickle_data))

        if obj_class := dct.get("__apscheduler_class__"):
            if obj_state := dct.get("__apscheduler_state__"):
                obj_class = ref_to_obj(obj_class)
                obj = object.__new__(obj_class)
                obj.__setstate__(obj_state)
                return obj

        return dct

    jobstore = self._jobstores[jobstore]
    with ExitStack() as stack:
        # if not hasattr(infile, "read"):
        #     infile = stack.enter_context(open(infile))

        j = json_store_get(key)

        data = json.loads(j, object_hook=json_object_hook)
        if not isinstance(data, dict):
            raise ValueError()

        if (version := data.get("version", None)) != 1:
            raise ValueError(f"unrecognized version: {version}")

        for job_state in data["jobs"]:
            job = object.__new__(Job)
            job.__setstate__(job_state)
            jobstore.add_job(job)


BaseScheduler.to_json = to_json
BaseScheduler.import_from_db = import_from_db


def scheduler_to_json(scheduler):
    scheduler.print_jobs()
    return scheduler.to_json()


def db_to_scheduler(scheduler, key):
    scheduler.import_from_db(key)

import datetime

from tests.base import ApiDBTestCase

from zou.app.utils import events

from zou.app.models.task import Task


class RouteTaskChangeTestCase(ApiDBTestCase):

    def setUp(self):
        super(RouteTaskChangeTestCase, self).setUp()

        self.generate_fixture_project_status()
        self.generate_fixture_project()
        self.generate_fixture_entity_type()
        self.generate_fixture_entity()
        self.generate_fixture_sequence()
        self.generate_fixture_shot()
        self.generate_fixture_department()
        self.generate_fixture_task_type()
        self.generate_fixture_task_status()
        self.generate_fixture_task_status_wip()
        self.generate_fixture_person()
        self.generate_fixture_assigner()
        self.generate_fixture_task()

        self.open_status_id = str(self.task_status.id)
        self.wip_status_id = str(self.task_status_wip.id)

        self.is_event_fired = False
        events.unregister_all()

    def handle_event(self, data):
        self.is_event_fired = True
        self.assertEqual(
            data["task_before"]["task_status_id"],
            self.open_status_id
        )
        self.assertEqual(
            data["task_after"]["task_status_id"],
            self.wip_status_id
        )

    def assert_event_is_fired(self):
        self.assertTrue(self.is_event_fired)

    def test_status_to_wip(self):
        self.task.real_start_date = None
        events.register(
            "task:start",
            "mark_event_as_fired",
            self
        )

        now = datetime.datetime.now()
        self.put("/actions/tasks/%s/start" % self.task.id, {})
        task = self.get("data/tasks/%s" % self.task.id)

        self.assertEqual(task["task_status_id"], self.wip_status_id)
        self.assertGreater(task["real_start_date"], now.isoformat())
        self.assert_event_is_fired()

    def test_status_to_wip_again(self):
        self.task.real_start_date = None
        self.put("/actions/tasks/%s/start" % self.task.id, {})
        real_start_date = Task.get(self.task.id).real_start_date
        self.put("/actions/tasks/%s/start" % self.task.id, {})
        task = self.get("data/tasks/%s" % self.task.id)
        self.assertEquals(real_start_date.isoformat(), task["real_start_date"])

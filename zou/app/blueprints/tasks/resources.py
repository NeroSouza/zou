from flask import abort, request
from flask_restful import Resource, reqparse
from flask_jwt_extended import jwt_required

from zou.app.services.exception import (
    TaskNotFoundException,
    PersonNotFoundException,
    MalformedFileTreeException,
    WrongDateFormatException
)
from zou.app.services import (
    tasks_service,
    shots_service,
    assets_service,
    persons_service,
    projects_service,
    files_service,
    file_tree_service,
    user_service,
    entities_service
)
from zou.app.utils import query, events, permissions


class CommentTaskResource(Resource):

    @jwt_required
    def post(self, task_id):
        (
            task_status_id,
            comment,
            person_id
        ) = self.get_arguments()

        tasks_service.get_task(task_id)
        if not permissions.has_manager_permissions():
            user_service.check_assigned(task_id)
        task_status = tasks_service.get_task_status(task_status_id)
        if person_id:
            person = persons_service.get_person(person_id)
        else:
            person = persons_service.get_current_user()
        comment = tasks_service.create_comment(
            object_id=task_id,
            object_type="Task",
            task_status_id=task_status_id,
            person_id=person["id"],
            text=comment
        )

        tasks_service.update_task(
            task_id,
            {"task_status_id": task_status_id}
        )

        comment["task_status"] = task_status
        comment["person"] = person
        events.emit("comment:new", {"id": comment["id"]})
        return comment, 201

    def get_arguments(self):
        parser = reqparse.RequestParser()
        parser.add_argument(
            "task_status_id",
            required=True,
            help="Task Status ID is missing"
        )
        parser.add_argument("comment", default="")
        parser.add_argument("person_id", default="")
        args = parser.parse_args()

        return (
            args["task_status_id"],
            args["comment"],
            args["person_id"]
        )


class AddPreviewResource(Resource):

    @jwt_required
    def post(self, task_id, comment_id):
        is_movie = self.get_arguments()

        task = tasks_service.get_task(task_id)
        if not permissions.has_manager_permissions():
            user_service.check_assigned(task_id)

        comment = tasks_service.get_comment(comment_id)
        task_status = tasks_service.get_task_status(
            comment.task_status_id
        )
        person = persons_service.get_current_user()

        if not task_status["is_reviewable"]:
            return {
                "error": "Comment status is not reviewable, you cannot link a "
                         "preview to it."
            }, 400

        revision = tasks_service.get_next_preview_revision(task_id)
        preview = files_service.create_preview_file(
            task["name"],
            revision,
            task["id"],
            person["id"],
            is_movie
        )
        comment.update({"preview_file_id": preview["id"]})
        events.emit("preview:add", {
            "comment_id": comment_id,
            "task_id": task_id,
            "preview": preview
        })

        return preview, 201

    def get_arguments(self):
        parser = reqparse.RequestParser()
        parser.add_argument("is_movie", type=bool, default=False)
        args = parser.parse_args()

        return args["is_movie"]


class TaskPreviewsResource(Resource):

    @jwt_required
    def get(self, task_id):
        task = tasks_service.get_task(task_id)
        if not permissions.has_manager_permissions():
            user_service.check_has_task_related(task["project_id"])
        return files_service.get_preview_files_for_task(task_id)


class TaskCommentsResource(Resource):

    @jwt_required
    def get(self, task_id):
        if not permissions.has_manager_permissions():
            user_service.check_has_task_related(task_id)
        return tasks_service.get_comments(task_id)


class PersonTasksResource(Resource):

    @jwt_required
    def get(self, person_id):
        if not permissions.has_manager_permissions():
            projects = user_service.related_projects()
        else:
            projects = projects_service.open_projects()
        return tasks_service.get_person_tasks(person_id, projects)


class PersonDoneTasksResource(Resource):

    @jwt_required
    def get(self, person_id):
        if not permissions.has_manager_permissions():
            projects = user_service.related_projects()
        else:
            projects = projects_service.open_projects()
        return tasks_service.get_person_done_tasks(person_id, projects)


class CreateShotTasksResource(Resource):

    @jwt_required
    def post(self, task_type_id):
        permissions.check_manager_permissions()
        criterions = query.get_query_criterions_from_request(request)
        shots = shots_service.get_shots(criterions)
        task_type = tasks_service.get_task_type(task_type_id)
        tasks = [
            tasks_service.create_task(task_type, shot) for shot in shots
        ]
        return tasks, 201


class CreateAssetTasksResource(Resource):

    @jwt_required
    def post(self, task_type_id):
        permissions.check_manager_permissions()
        criterions = query.get_query_criterions_from_request(request)
        assets = assets_service.get_assets(criterions)
        task_type = tasks_service.get_task_type(task_type_id)
        tasks = [
            tasks_service.create_task(task_type, asset)
            for asset in assets
        ]
        return tasks, 201


class ToReviewResource(Resource):

    @jwt_required
    def put(self, task_id):
        (person_id, comment, working_file_id) = self.get_arguments()

        try:
            task = tasks_service.get_task(task_id)
            if not permissions.has_manager_permissions():
                user_service.check_assigned(task_id)

            person = persons_service.get_person(person_id)

            preview_path = ""
            if working_file_id is not None:
                working_file = files_service.get_working_file(working_file_id)
                software = files_service.get_software(
                    working_file["software_id"]
                )
                revision = working_file["revision"]

                preview_path = self.get_preview_path(
                    task,
                    working_file["name"],
                    revision,
                    software
                )

            task = tasks_service.task_to_review(
                task["id"],
                person,
                comment,
                preview_path
            )
        except PersonNotFoundException:
            return {"error": "Cannot find given person."}, 400

        return task

    def get_preview_path(self, task, name, revision, software):
        try:
            folder_path = file_tree_service.get_folder_path(
                task,
                mode="preview",
                software=software
            )
            file_name = file_tree_service.get_file_name(
                task,
                name=name,
                mode="preview",
                software=software,
                version=revision
            )
        except MalformedFileTreeException:  # No template for preview files.
            return {"folder_path": "", "file_name": ""}

        return {
            "folder_path": folder_path,
            "file_name": file_name
        }

    def get_arguments(self):
        parser = reqparse.RequestParser()
        parser.add_argument("person_id", default="")
        parser.add_argument("comment", default="")
        parser.add_argument("working_file_id", default=None)
        args = parser.parse_args()

        return (
            args["person_id"],
            args["comment"],
            args["working_file_id"]
        )


class ClearAssignationResource(Resource):

    @jwt_required
    def put(self):
        (task_ids) = self.get_arguments()

        for task_id in task_ids:
            try:
                tasks_service.clear_assignation(task_id)
            except TaskNotFoundException:
                pass
        return task_ids

    def get_arguments(self):
        parser = reqparse.RequestParser()
        parser.add_argument(
            "task_ids",
            help="Tasks list required.",
            required=True,
            action="append"
        )
        args = parser.parse_args()
        return (
            args["task_ids"]
        )


class TasksAssignResource(Resource):

    @jwt_required
    def put(self, person_id):
        (task_ids) = self.get_arguments()

        tasks = []
        for task_id in task_ids:
            try:
                task = self.assign_task(task_id, person_id)
                tasks.append(task)
            except TaskNotFoundException:
                pass
            except PersonNotFoundException:
                return {"error": "Assignee doesn't exist in database."}, 400

        return tasks

    def get_arguments(self):
        parser = reqparse.RequestParser()
        parser.add_argument(
            "task_ids",
            help="Tasks list required.",
            required=True,
            action="append"
        )
        args = parser.parse_args()
        return (
            args["task_ids"]
        )

    def assign_task(self, task_id, person_id):
        return tasks_service.assign_task(task_id, person_id)


class TaskAssignResource(Resource):

    @jwt_required
    def put(self, task_id):
        (person_id) = self.get_arguments()

        try:
            permissions.check_manager_permissions()
            task = self.assign_task(task_id, person_id)
        except PersonNotFoundException:
            return {"error": "Assignee doesn't exist in database."}, 400

        return task

    def get_arguments(self):
        parser = reqparse.RequestParser()
        parser.add_argument(
            "person_id",
            help="Assignee ID required.",
            required=True
        )
        args = parser.parse_args()

        return (
            args.get("person_id", ""),
        )

    def assign_task(self, task_id, person_id):
        return tasks_service.assign_task(task_id, person_id)


class TaskFullResource(Resource):

    @jwt_required
    def get(self, task_id):
        task = tasks_service.get_task(task_id)
        if not permissions.has_manager_permissions():
            user_service.check_has_task_related(task["project_id"])

        result = task
        task_type = tasks_service.get_task_type(task["task_type_id"])
        result["task_type"] = task_type
        assigner = persons_service.get_person(task["assigner_id"])
        result["assigner"] = assigner
        project = projects_service.get_project(task["project_id"])
        result["project"] = project
        task_status = tasks_service.get_task_status(task["task_status_id"])
        result["task_status"] = task_status
        entity = tasks_service.get_entity(task["entity_id"])
        result["entity"] = entity
        if entity["parent_id"] is not None:
            sequence = shots_service.get_sequence(entity["parent_id"])
            result["sequence"] = sequence
            if sequence["parent_id"] is not None:
                episode = shots_service.get_episode(sequence["parent_id"])
                result["episode"] = episode
        entity_type = tasks_service.get_entity_type(entity["entity_type_id"])
        result["entity_type"] = entity_type
        assignees = []
        for assignee_id in task["assignees"]:
            assignees.append(persons_service.get_person(assignee_id))
        result["persons"] = assignees
        result["type"] = "Task"

        return result, 200


class TaskStartResource(Resource):

    @jwt_required
    def put(self, task_id):
        task = tasks_service.get_task(task_id)
        if not permissions.has_manager_permissions():
            user_service.check_assigned(task_id)
        return tasks_service.start_task(task["id"])


class TaskForEntityResource(Resource):

    @jwt_required
    def get(self, entity_id, task_type_id):
        entity = entities_service.get_entity(entity_id)
        if not permissions.has_manager_permissions():
            user_service.check_has_task_related(entity["project_id"])
        return tasks_service.get_tasks_for_entity_and_task_type(
            entity_id,
            task_type_id
        )


class SetTimeSpentResource(Resource):

    @jwt_required
    def post(self, task_id, date, person_id):
        args = self.get_arguments()

        try:
            if not permissions.has_manager_permissions():
                user_service.check_assigned(task_id)
            tasks_service.get_task(task_id)
            persons_service.get_person(person_id)
            time_spent = tasks_service.create_or_update_time_spent(
                task_id,
                person_id,
                date,
                args["duration"]
            )
            return time_spent, 200
        except WrongDateFormatException:
            abort(404)

    def get_arguments(self):
        parser = reqparse.RequestParser()
        parser.add_argument("duration", default=0)
        args = parser.parse_args()
        return args


class AddTimeSpentResource(Resource):

    @jwt_required
    def post(self, task_id, date, person_id):
        args = self.get_arguments()

        try:
            tasks_service.get_task(task_id)
            if not permissions.has_manager_permissions():
                user_service.check_assigned(task_id)

            persons_service.get_person(person_id)
            time_spent = tasks_service.create_or_update_time_spent(
                task_id,
                person_id,
                date,
                args["duration"],
                add=True
            )
            return time_spent, 200
        except WrongDateFormatException:
            abort(404)

    def get_arguments(self):
        parser = reqparse.RequestParser()
        parser.add_argument("duration", default=0, type=int)
        args = parser.parse_args()
        return args


class GetTimeSpentResource(Resource):

    @jwt_required
    def get(self, task_id, date):
        try:
            task = tasks_service.get_task(task_id)
            if not permissions.has_manager_permissions():
                user_service.check_has_task_related(task.project_id)
            return tasks_service.get_time_spents(task_id)
        except WrongDateFormatException:
            abort(404)

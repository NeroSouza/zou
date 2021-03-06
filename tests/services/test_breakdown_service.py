from tests.base import ApiDBTestCase

from zou.app.services import breakdown_service


class BreakdownServiceTestCase(ApiDBTestCase):

    def setUp(self):
        super(BreakdownServiceTestCase, self).setUp()
        self.generate_fixture_project_status()
        self.generate_fixture_project()
        self.generate_fixture_entity_type()
        self.generate_fixture_asset_types()
        self.generate_fixture_episode()
        self.generate_fixture_sequence()
        self.generate_fixture_shot()
        self.generate_fixture_scene()
        self.generate_fixture_entity()
        self.generate_fixture_entity_character()
        self.shot_id = str(self.shot.id)
        self.scene_id = str(self.scene.id)
        self.entity_id = str(self.entity.id)
        self.entity_character_id = str(self.entity_character.id)

    def new_shot_instance(self, asset_id):
        return breakdown_service.add_asset_instance_to_shot(
            self.shot_id, asset_id
        )

    def new_scene_instance(self, asset_id):
        return breakdown_service.add_asset_instance_to_scene(
            self.scene_id, asset_id
        )

    def test_update_casting(self):
        self.shot_id = str(self.shot.id)
        self.entity_id = str(self.entity.id)
        self.entity_character_id = str(self.entity_character.id)

        casting = breakdown_service.get_casting(self.shot.id)
        self.assertListEqual(casting, [])
        new_casting = [
            {
                "asset_id": self.entity_id,
                "nb_occurences": 1
            },
            {
                "asset_id": self.entity_character_id,
                "nb_occurences": 3
            }
        ]
        breakdown_service.update_casting(self.shot.id, new_casting)

        casting = breakdown_service.get_casting(self.shot.id)
        casting = sorted(casting, key=lambda x: x["nb_occurences"])
        self.assertEquals(casting[0]["asset_id"], new_casting[0]["asset_id"])
        self.assertEquals(
            casting[0]["nb_occurences"],
            new_casting[0]["nb_occurences"]
        )
        self.assertEquals(casting[1]["asset_id"], new_casting[1]["asset_id"])
        self.assertEquals(
            casting[1]["nb_occurences"],
            new_casting[1]["nb_occurences"]
        )
        self.assertEquals(
            casting[1]["asset_name"],
            self.entity_character.name
        )
        self.assertEquals(
            casting[1]["asset_type_name"],
            self.entity_type_character.name
        )

        cast_in = breakdown_service.get_cast_in(self.entity_character.id)
        self.assertEquals(cast_in[0]["shot_name"], self.shot.name)
        self.assertEquals(cast_in[0]["sequence_name"], self.sequence.name)
        self.assertEquals(cast_in[0]["episode_name"], self.episode.name)

    def test_add_instance_to_shot(self):
        instances = breakdown_service.get_asset_instances_for_shot(self.shot.id)
        self.assertEquals(instances, {})

        self.new_shot_instance(self.entity_id)
        self.new_shot_instance(self.entity_id)
        self.new_shot_instance(self.entity_character_id)

        instances = breakdown_service.get_asset_instances_for_shot(self.shot.id)
        self.assertEquals(len(instances[self.entity_id]), 2)
        self.assertEquals(len(instances[self.entity_character_id]), 1)
        self.assertEquals(instances[self.entity_id][0]["number"], 1)
        self.assertEquals(instances[self.entity_id][1]["number"], 2)
        self.assertEquals(instances[self.entity_character_id][0]["number"], 1)

    def test_get_shot_asset_instances_for_asset(self):
        instances = breakdown_service.get_shot_asset_instances_for_asset(
            self.entity.id
        )
        self.assertEquals(instances, {})

        self.new_shot_instance(self.entity.id)
        self.new_shot_instance(self.entity.id)
        self.new_shot_instance(self.entity_character.id)
        instances = breakdown_service.get_shot_asset_instances_for_asset(
            self.entity.id
        )
        self.assertEquals(len(instances[self.shot_id]), 2)

    def test_add_instance_to_scene(self):
        instances = breakdown_service.get_asset_instances_for_scene(
            self.scene.id
        )
        self.assertEquals(instances, {})

        self.new_scene_instance(self.entity_id)
        self.new_scene_instance(self.entity_id)
        self.new_scene_instance(self.entity_character_id)

        instances = breakdown_service.get_asset_instances_for_scene(
            self.scene.id
        )
        self.assertEquals(len(instances[self.entity_id]), 2)
        self.assertEquals(len(instances[self.entity_character_id]), 1)
        self.assertEquals(instances[self.entity_id][0]["number"], 1)
        self.assertEquals(instances[self.entity_id][1]["number"], 2)
        self.assertEquals(instances[self.entity_character_id][0]["number"], 1)

    def test_get_scene_asset_instances_for_asset(self):
        instances = breakdown_service.get_scene_asset_instances_for_asset(
            self.entity.id
        )
        self.assertEquals(instances, {})

        self.new_scene_instance(self.entity.id)
        self.new_scene_instance(self.entity.id)
        self.new_scene_instance(self.entity_character.id)
        instances = breakdown_service.get_scene_asset_instances_for_asset(
            self.entity.id
        )
        self.assertEquals(len(instances[self.scene_id]), 2)

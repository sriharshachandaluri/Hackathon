import unittest

from website_generator.config import MAX_REPAIR_ITERATIONS
from website_generator.agents.manager_agent.agent import integration_testing_loop, manager_agent


class WorkflowStructureTests(unittest.TestCase):
    def test_manager_runs_scope_agent_before_frontend_validation_loop(self):
        self.assertEqual([agent.name for agent in manager_agent.sub_agents], [
            "manager_analysis", "development_integration_test_loop", "runner_agent"
        ])
        self.assertEqual([agent.name for agent in integration_testing_loop.sub_agents], [
            "frontend_agent", "integration_agent", "testing_agent"
        ])

    def test_pipeline_has_no_server_or_database_implementation_agents(self):
        agent_names = {agent.name for agent in manager_agent.sub_agents}
        loop_names = {agent.name for agent in integration_testing_loop.sub_agents}
        self.assertFalse(any("backend" in name or "database" in name
                             for name in agent_names | loop_names))

    def test_repair_loop_uses_configured_iteration_limit(self):
        self.assertEqual(integration_testing_loop.max_iterations, MAX_REPAIR_ITERATIONS)
        self.assertGreaterEqual(MAX_REPAIR_ITERATIONS, 1)


if __name__ == "__main__":
    unittest.main()

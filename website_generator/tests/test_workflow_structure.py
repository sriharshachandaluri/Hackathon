from website_generator.agents.manager_agent.agent import manager_agent, parallel_development


def test_parallel_development_contains_three_independent_agents():
    assert parallel_development.name == "parallel_development"
    assert {agent.name for agent in parallel_development.sub_agents} == {
        "frontend_agent", "backend_agent", "database_agent"
    }


def test_manager_orders_spec_parallel_integration_testing_deployment():
    names = [agent.name for agent in manager_agent.sub_agents]
    assert names == [
        "manager_analysis", "development_integration_test_loop", "deployment_agent"
    ]

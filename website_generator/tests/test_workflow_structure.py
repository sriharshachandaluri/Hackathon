from website_generator.agents.manager_agent.agent import manager_agent, development_agents


def test_sequential_development_contains_three_independent_agents():
    assert development_agents.name == "development_agents_sequential"
    assert {agent.name for agent in development_agents.sub_agents} == {
        "frontend_agent", "backend_agent", "database_agent"
    }


def test_manager_orders_spec_parallel_integration_testing_deployment():
    names = [agent.name for agent in manager_agent.sub_agents]
    assert names == [
        "manager_analysis", "development_integration_test_loop", "deployment_agent"
    ]

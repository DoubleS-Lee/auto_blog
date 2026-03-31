from crewai import Agent, Crew, Process, Task, LLM
from crewai.project import CrewBase, agent, crew, task
from tools import (
    NaverDataLabTool,
    NaverSearchTool,
    SajuDataTool,
    GeminiImageGeneratorTool,
    ExifInjectorTool,
    NaverSmartEditorTool,
)


@CrewBase
class BlogAutomationCrew:
    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"

    def _llm(self):
        return LLM(model="gemini/gemini-3.1-flash-lite-preview")

    @agent
    def seo_analyst(self) -> Agent:
        return Agent(
            config=self.agents_config["seo_analyst"],
            llm=self._llm(),
            tools=[NaverDataLabTool(), NaverSearchTool()],
            allow_delegation=False,
            cache=False,
            verbose=True,
        )

    @agent
    def content_writer(self) -> Agent:
        return Agent(
            config=self.agents_config["content_writer"],
            llm=self._llm(),
            tools=[SajuDataTool()],
            allow_delegation=False,
            cache=False,
            verbose=True,
        )

    @agent
    def image_creator(self) -> Agent:
        return Agent(
            config=self.agents_config["image_creator"],
            llm=self._llm(),
            tools=[GeminiImageGeneratorTool(), ExifInjectorTool()],
            allow_delegation=False,
            cache=False,
            verbose=True,
        )

    @agent
    def seo_optimizer(self) -> Agent:
        return Agent(
            config=self.agents_config["seo_optimizer"],
            llm=self._llm(),
            tools=[],
            allow_delegation=False,
            cache=False,
            verbose=True,
        )

    @agent
    def blog_publisher(self) -> Agent:
        return Agent(
            config=self.agents_config["blog_publisher"],
            llm=self._llm(),
            tools=[NaverSmartEditorTool()],
            allow_delegation=False,
            cache=False,
            verbose=True,
        )

    @task
    def keyword_research_task(self) -> Task:
        return Task(config=self.tasks_config["keyword_research_task"])

    @task
    def content_writing_task(self) -> Task:
        return Task(config=self.tasks_config["content_writing_task"])

    @task
    def image_generation_task(self) -> Task:
        return Task(config=self.tasks_config["image_generation_task"])

    @task
    def seo_optimization_task(self) -> Task:
        return Task(config=self.tasks_config["seo_optimization_task"])

    @task
    def blog_publishing_task(self) -> Task:
        return Task(config=self.tasks_config["blog_publishing_task"])

    @crew
    def crew(self) -> Crew:
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=True,
        )

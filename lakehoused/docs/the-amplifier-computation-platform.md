# The Amplifier Computing Platform (ACP)

Paul Payne

## Introduction

Recently, the MADE:Explorations team developed Amplifier, a configurable AI orchestration system consisting of the Amplifier-Core which takes configurations and runs agent workflows with them, and the Amplifier CLI, a command line interface used to interact with Amplifier Core with a similar UX to Claude Code or other command-line agentic tools.
This paper discusses the development of the Amplifier Computing Platform, which uses the Amplifier Core within a locally-running webservice (the Amplifier Daemon or lakehoused) and exposes a user interface through a local web application.

The Amplifier Computing Platform (ACP) is a glimpse of the vision of the intelligent computing platform of the (near) future.

## Computation for the People

Since the dawn of the Turing machine theoretical model and the Von Neumann architecture, we have been working to make computation more accessible to everyday people. The compiler, high-level languages, the filesystem, the command line, the GUI desktop (WIMP) all allowed more and more people to use computers to accomplish their goals.

But it still took specialists to write code, so the application model, with its corresponding app distribution models (culminating in app stores and web apps), became the preferred way to make computation accessible to the masses. Since people couldn’t write their own software, they could at least buy apps from people who could. The “app” became the basic unit of interaction.

But now, agentic systems can write custom apps on the fly. The user is no longer locked into whatever apps are available on the marketplace. They no longer need to stitch together a workflow with the apps at hand. They can interact with the computer directly to have it meet their goals.

Moreover, agentic systems have the ability to learn from usage, improve workflows, and automate meta-tasks in ways that only consultants or engineering staff were able to do previously.

For the first time, users can just interact with a computer and ask it to do what they want and have it automatically build the computational systems that support their workflows—directly.

## Recent Developments in Agentic Computation

ChatGPT, Claude, Semantic Workbench, and other AI apps provide a simple natural language interface for interacting with a language model. These apps suffer from being isolated within the app box. They run on systems far away, isolated from your own computers. MCP, tools, and plugins are attempts to give the chat apps more access to your custom data or cloud applications. These integrations require custom context to be fed to the app assistants so they know how to use the exposed integrations. They all require strict security mechanisms. This is so much work.
Alternatively, Claude Code, and similar command-line tools run directly on your computer, offloading their LLM calls to the cloud. LLMs already know how to use the command line, and the command line can still do pretty much anything a user would want on a computer, so this is an immediate way to give assistants vast capability without needing to write integrations. Assistants relieve users from becoming command line experts.

Coding agents add context and tools to assistants that make them more capable for coding tasks. Most recently, developers are providing ways to extend this context and tooling (AGENTS.md files, @mentions, skills, etc.) to make the agents more capable for a variety of non-coding tasks.

MADE:Exploration has been thinking about this process at a meta-level. Developers shouldn’t be figuring out how to extend an agentic platform, the agents should. To this end, we have experimented with techniques and patterns with our Amplifier v1, and have released early versions of Amplifier Core and Amplifier CLI that work with these patterns. With Amplifier, you can work at a low level, swapping out not just tools and context, but the entire orchestration loop, memory systems, and more; and you can also work at a high level—encoding entire automated workflows and having the agent modify it’s own tooling and behavior as it learns from your interactions.

## The Intelligent Computation Platform

What we really want is to be able to interact with a computer in a natural way: simply specify our goals and have the computer help us achieve them. We want data created, gathered, organized, transformed, operationalized, and projected in all the ways useful to us.

We might start with a basic set of capabilities: agents can manage our data, can write and run programs, and remember what we’ve done with them. But, when we get tired of asking an agent to do everything step by step, we want to start stitching together some workflows and be able to just ask it to do all the steps at once. But then when we get tired of asking it to create and run workflows, we’ll want it to help us know when a workflow or new tool is necessary and proactively design and run them for us.

The work of our lives is made up of interconnected projects and subprojects, often very different from one another. We have one set of systems for healthcare, another for family, or finances, or personal development, or software development. We’ll have different workflows for different projects and we’ll want the agents to remember all the things about each project; what it is for, how it works, what we’ve accomplished so far, what is left to do. Having assistants develop unique capabilities for each context is a challenging problem, but this is exactly what we can expect from an intelligent computation platform.

And we want our computers to be proactive: scheduling, monitoring, suggesting, and most of all always making forward progress on our objectives, looping us in as necessary to clarify and expand on our wishes.
Developing ACP, the Intelligent Computation Platform

Repository: payneio/lakehoused: Amplifier daemon w/ learning resources.

This repo contains a culmination of my thoughts about the Amplifier Computation Platform (ACP). It consists of a web service daemon (lakehoused), a web app, and supporting documentation.

The daemon exposes a RESTful web API and encompasses many of the ideas of a computation platform while managing interaction with the Amplifier Core. Specifically:

### Expertise in endless domains

Contextualizing and personalizing the behavior of agents is important so it must be easy to make even hundreds of various profiles for different situations. The state of agents is changing all the time and we should be able to easily pull in additional capabilities as needed. Amplifier Core provides the flexibility to compose agent behavior from multiple sources, and the ACP makes this composition accessible to the user.

Users are provided with a set of starter profiles, but they can copy them or create new ones from scratch, using any Amplifier Core module they can find or have their agents create.

The profile can be switched within any chat session at any time allowing the same chat to vary in expertise and behavior as needed.

Profiles are agent behavior, not project context. Unlike other agentic systems, ACP keeps these distinct.

### My data is not your agent (personal data lakehouse)

ACP is designed to work on your data. You provide the daemon a path to a data directory and any directory within it can be amplified, turning it into a project known by the ACP. Amplifying a directory means you can start chat sessions in it and the agent will be personalized for that project. Sessions in projects will have default profiles, custom context, and provide a natural point to attach project-specific workflows and automation. Your sessions become vital historical context for the project. Most importantly, your project is a file directory and can contain any files with any organization that you’d like and your agent will be aware of how you work with it.

The power of a personal data lakehouse cannot be overstated in an intelligent computation platform. In addition to privacy and control, your personal data lakehouse becomes a natural integration point able to receive sync’d data from any data systems you interact with. If you sync your calendar, your email, your One Drive, your photos, your personal or team projects, they are immediately accessible and amplified with ACP.

### A computing platform never sleeps (the daemon)

Existing coding agents work only when you push them. Since the ACP is a daemon, it is always running. Because of this, we can add reactivity and meta-activity. You can schedule workflows to happen periodically. Workflows can be kicked off when various conditions occur (you can define them all with your assistant). Do you want your own newspaper to be created from your favorite sources and made ready for every morning? Do you want new customer leads to have dossiers created for you along with introductory emails? Do you want ACP to review it’s performance each evening and suggest additional profiles, tools, or context adjustments to make it work better? All of these things, and any other workflow or computational tool you can imagine, is possible.

### An interface for the people (running locally)

Interacting with your computer should be on your terms. Your interface should not be someone else’s app, someone else’s operating system. Why not tell ACP how you want your UI to be laid out and have it make it for you?

ACP is not installed like a typical app. Instead, you always run it in “dev mode”. It’s dynamic and can be rewritten according to your instructions. Do you want a single dashboard greeting you? Do you want specific tools or functionality at your disposal? The UI for each project can be customized, as can any part of the entire ACP system.

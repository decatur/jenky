namespace jenky {
    interface Process {
        name: string,
        running: boolean,
        createTime: number
    }

    interface GitRef {
        refName: string,
        creatorDate: string
    }

    interface Repo {
        repoName: string,
        gitRef: string,
        gitRefs: GitRef[],
        gitMessage: string,
        processes: Process[]
    }

    interface RepoDict {
        [id: string] : Repo;
    }
}
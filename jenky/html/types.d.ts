namespace jenky {
    interface Process {
        name: string,
        running: boolean,
        createTime: number
    }
    interface Repo {
        repoName: string,
        gitTag: string,
        gitTags: string[],
        gitBranches: string[],
        gitMessage: string,
        processes: Process[]
    }
    interface RepoDict {
        [id: string] : Repo;
    }
}
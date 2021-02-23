namespace jenky {
    interface Process {
        name: string,
        running: boolean,
        createTime: number
        serviceUrl: string
    }

    interface GitRef {
        refName: string,
        creatorDate: string
    }

    interface Repo {
        repoName: string,
        remoteUrl: string,
        gitRef: string,
        gitRefs: GitRef[],
        gitMessage: string,
        processes: Process[]
    }

}
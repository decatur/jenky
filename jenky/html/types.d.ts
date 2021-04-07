declare namespace jenky {
    interface Process {
        name: string,
        running: boolean,
        createTime: number
        serviceSubDomain: string
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
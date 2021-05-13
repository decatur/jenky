declare namespace jenky {
    interface Process {
        name: string;
        createTime: number;
        keepRunning: boolean;
        serviceSubDomain: string;
        serviceHomePath: string;
    }

    interface GitRef {
        refName: string;
        creatorDate: string;
    }

    interface Repo {
        repoName: string;
        remoteUrl: string;
        gitRef: string;
        gitRefs: GitRef[];
        gitMessage: string;
        processes: Process[];
    }
}
import os
import logging
import shutil
import requests
from tqdm import tqdm
from zipfile import ZipFile
from pathlib import Path
from ebbs import Builder, OtherBuildError

# Class name is what is used at cli, so we defy convention here in favor of ease-of-use.
class boilerplate(Builder):
    def __init__(this, name="Boilerplate"):
        super().__init__(name)

        this.supportedProjectTypes = []
        this.clearBuildPath = False
        
    def DidBuildSucceed(this):
        return True #TODO: Make sure that all files were created.


    # Required Builder method. See that class for details.
    def Build(this):
        os.chdir(this.rootPath)
        this.SetupCommonFolders()
        this.SetupWorkflows()
        this.SetupBuild()
        this.SetupGitignore()
        this.Cleanup()

    # Create commonly used folders in the root of the repo
    def SetupCommonFolders(this):
        paths = [
            '.github',
            'exe',
            'build',
            'build/config',
            'inc',
            'lib',
            'src',
            'test',
            'tmp' #will be deleted.
        ]
        for path in paths:
            Path(path).mkdir(parents=True, exist_ok=True)


    # Create .github/workflows folder
    # Code copied from eons. TODO: Consider consolidating upstream.
    def SetupWorkflows(this):
        packageZipPath = "./tmp/ebbs.workflows.part-main.zip"

        url = "https://github.com/eons-dev/ebbs.workflows.part/archive/refs/heads/main.zip"

        headers = {
            "Connection": "keep-alive",
        }     

        packageQuery = requests.get(url, headers=headers, stream=True)

        if (packageQuery.status_code != 200):
            logging.error(f"Got {packageQuery.status_code}; unable to download github workflows.")
            raise OtherBuildError("Unable to download github workflows.")

        packageSize = int(packageQuery.headers.get('content-length', 0))
        chunkSize = 1024 #1 Kibibyte

        logging.debug(f"Writing {packageZipPath} ({packageSize} bytes)")
        packageZipContents = open(packageZipPath, 'wb+')
        
        progressBar = None
        if (this.executor.verbosity >= 2):
            progressBar = tqdm(total=packageSize, unit='iB', unit_scale=True)

        for chunk in packageQuery.iter_content(chunkSize):
            packageZipContents.write(chunk)
            if (this.executor.verbosity >= 2):
                progressBar.update(len(chunk))
        
        if (this.executor.verbosity >= 2):
            progressBar.close()

        if (packageSize and this.executor.verbosity >= 2 and progressBar.n != packageSize):
            logging.error(f"Package wrote {progressBar.n} / {packageSize} bytes")
            raise OtherBuildError("Github workflows package not fully written.")
        
        packageZipContents.close()

        if (not os.path.exists(packageZipPath)):
            logging.error(f"Failed to create {packageZipPath}")
            raise OtherBuildError("Github workflows zip was not created.")

        logging.debug(f"Extracting {packageZipPath}")
        openArchive = ZipFile(packageZipPath, 'r')
        extractLoc = './.github/'
        openArchive.extractall(f"{extractLoc}")
        openArchive.close()
        #zip will be deleted in Cleanup()
        os.rename("./.github/ebbs.workflows.part-main", "./.github/workflows")


    # Create /build folder
    def SetupBuild(this):
        buildFile = this.CreateFile('./build/build.json')
        buildFile.write(f'''{{
  "name" : "{this.projectName}",
  "type" : "{this.projectType}",
''')
        buildFile.write('''\
  "clear_build_path" : true,
  "build_in" : "tmp",
  "next": [
    {
      "run_when_none" : [
        "github"
      ],
      "build" : "proxy",
      "build_in" : "local",
      "config" : {
        "clear_build_path" : false,
        "proxy" : "../config/local.json"
      }
    },
    {
      "run_when_any" : [
        "github"
      ],
      "build" : "proxy",
      "build_in" : "github",
      "config" : {
        "clear_build_path" : false,
        "proxy" : "../config/github.json"
      }
    }
  ]
}
''')
        buildFile.close()

        githubBuildFile = this.CreateFile('./build/config/github.json')
        githubBuildFile.write('''{
  "next": [
    {
      "run_when_any" : [
        "push",
        "pull_request",
        "release"
      ],
      "build" : "proxy",
      "build_in" : "local",
      "config" : {
        "clear_build_path" : false,
        "proxy" : "../../config/local.json"
      }
    },
    {
      "run_when_any" : [
        "schedule"
      ],
      "build" : "proxy",
      "build_in" : "schedule",
      "config" : {
        "clear_build_path" : false,
        "proxy" : "../../config/schedule.json"
      }
    }
  ]
}
''')
        githubBuildFile.close()

        localBuildFile = this.CreateFile('./build/config/local.json')
        localBuildFile.write('''{
    "_comment": "YOUR CODE GOES HERE"
}
''')
        localBuildFile.close()

        scheduleBuildFile = this.CreateFile('./build/config/schedule.json')
        scheduleBuildFile.write('''{
}
''')
        scheduleBuildFile.close()


    # Create .gitignore
    def SetupGitignore(this):
        gitignore = this.CreateFile(".gitignore")
        gitignore.write('''#build
build/**/
!/build/config/

#intellij
/.idea/
''')


    # Remove whatever this created
    def Cleanup(this):
        shutil.rmtree('./tmp')
        shutil.rmtree('./eons')

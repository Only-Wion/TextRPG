$DevLocalConfig = @{
    # Python interpreter that already has requirements.txt installed.
    PythonExe         = 'E:\TextRPG\.conda\envs\TextRPG-py311\python.exe'

    # Local PostgreSQL. URL-encode special characters in the password.
    PostgresDsn       = 'postgresql://textrpg_local:CHANGE_ME@127.0.0.1:5432/textrpg_local'

    # Alibaba Cloud OSS. Use the public endpoint for development on your PC.
    OssEndpoint       = 'https://oss-cn-hangzhou.aliyuncs.com'
    OssBucket         = 'CHANGE_ME'
    OssAccessKeyId    = 'CHANGE_ME'
    OssAccessKeySecret = 'CHANGE_ME'
    OssRegion         = 'cn-hangzhou'
    OssPrefix         = 'textrpg-local-dev'

    BackendHost       = '127.0.0.1'
    BackendPort       = 8000
    FrontendHost      = '127.0.0.1'
    FrontendPort      = 3000
    AdminHost         = '127.0.0.1'
    AdminPort         = 8501
}

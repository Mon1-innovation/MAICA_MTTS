I'm sorry for not offering an English ver of this document but it's just too much work for me.
If you want to read in English, use a translator.

此文档是MAICA-MTTS接口后端的部署文档, 编纂版本为v1.0.  
请注意该程序是协调通信程序, 模型需要另行部署. 自v1.0后, 仓库提供自动的release.
> 该项目使用[GPT-SoVITS](https://github.com/RVC-Boss/GPT-SoVITS)实现tts. 若你希望采用其它项目, 请自行修改源码逻辑.

自v1.0后, MAICA-MTTS不再需要独立部署, 其新的实现方式是作为MAICA的可选依赖. 以下流程中均假设你已部署MAICA后端.

该文档仅为有一定技术基础的用户讲解, 不会提供过于细致的指导.

+ 下载和安装:

    拉取仓库:

    ```
    git clone https://github.com/Mon1-innovation/MAICA_MTTS
    cd MAICA_MTTS
    ```

    安装:

    ```
    pip install -e .
    ```

    配置:

    ```
    maica -t create
    vim .env
    ```

    启动实例:

    ```
    maica tts -e .env
    ```

+ 或者, 直接通过pypi安装:

    > 便捷但不适合开发, 兼容性有待测试.

    安装:

    ```
    pip install mi-mtts
    ```

    配置:

    ```
    maica -t create
    vim .env
    ```

    启动实例:

    ```
    maica tts -e .env
    ```
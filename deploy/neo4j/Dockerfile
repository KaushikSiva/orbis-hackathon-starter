FROM neo4j:5.26-community
COPY deploy/neo4j/start.sh /showroom-start.sh
ENTRYPOINT ["tini", "-g", "--", "/bin/bash", "/showroom-start.sh"]
CMD ["neo4j"]

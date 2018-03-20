from bs4 import BeautifulSoup

infile = open("thefile.xml","r")
contents = infile.read()
soup = BeautifulSoup(contents, "xml")
excludes = ''
for exclusion in soup.find_all("exclusion"):
    excludes = excludes + "^" + exclusion.groupId.get_text() + ":" + exclusion.artifactId.get_text()

print(excludes)

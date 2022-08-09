from pathlib import Path

# Make the user roles plural, adding s. Not perfect because some names ends with a noun like 'operator, press' so the output will be 'operator, presss' instead of 'operators, press' but there are a couple of these occurrences in the whole data set.
def readfile(name):
    with open(name) as f:
        nf = open("user_roles.txt", "w+")
        for line in f:
            linex = line.strip() + 's'
            n_line = f'    - {linex}\n'
            nf.write(n_line)
        nf.close()

# Annotate the rasa entities in a userstory format
def annotate_userstories(name):
    nf = open("userstories.txt", "w+")
    entries = Path(f'{name}/')
    for entry in entries.iterdir():
        with open(f'{name}/{entry.name}') as f:
            for line in f:
                spline = splice(line)
                nf.write(spline)
    nf.close()

############ Helper functions #######################################################
def splice(string):
    if 'I want to' in string or 'I Want To' in string:
            rmv1 = string.replace('.', '')
            s = rmv1.replace(',', '')
            if 'so that' in s:
                return splice_full_story(s)
            elif 'So that' in s:
                sn = s.replace('So that', 'so that')
                return splice_full_story(sn)
            else:
                return splice_short_story(s)
    else:
        return ''


def splice_full_story(string):
    ls = string.split(' I want to ', 1)
    as_user = ls[0]
    func_benft = ls[1].split(' so that ', 1)
    func = func_benft[0]
    benft = func_benft[1].rstrip()

    if 'As a ' in as_user:
        user = as_user.replace('As a ','')
        return f'    - As a [{user}](user) I want to [{func}](functionality) so that [{benft}](benefit)\n'
    else:
        user = as_user.replace('As an ','')
        return f'    - As an [{user}](user) I want to [{func}](functionality) so that [{benft}](benefit)\n'

def splice_short_story(string):
    ls = string.split(' I want to ', 1)
    as_user = ls[0]
    func = ls[1].rstrip()

    if 'As a ' in as_user:
        user = as_user.replace('As a ','')
        return f'    - As a [{user}](user) I want to [{func}](functionality)\n'
    else:
        user = as_user.replace('As an ','')
        return f'    - As an [{user}](user) I want to [{func}](functionality)\n'



if __name__ == '__main__':
    annotate_userstories('userstories')
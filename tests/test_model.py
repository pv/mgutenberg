import mgutenberg.model as model

def test_transpose_articles():
    for s in [u',', u' --', u'\u2015']:
        assert (model.transpose_articles(u"The Adventures Sawyer%s Part 1"%s)
                                        == u"Adventures Sawyer, The%s Part 1"%s)

# Contributing to LArPix-Control

We welcome contributions from DUNE collaborators. Here's what you should
know.

## Reach out first

It's important to coordinate so you don't waste time implementing a
feature that someone else is already working on, or that we've already
decided not to use. Reach out to us so we can stay coordinated:

- Open an issue on GitHub
- Post on the #larpix channel on DUNE Slack
- Email Dan Dwyer or Peter Madigan

Make sure to include your name, institution, and how you'd like to
help.

## Workflow

We use a version of the
[OneFlow](https://www.endoflineblog.com/oneflow-a-git-branching-model-and-workflow)
Git branching model. It is summarized here, with the appropriate
commands to use:

1. Make a [fork](https://help.github.com/en/articles/fork-a-repo) of
larpix/larpix-control on GitHub and work from there

2. Clone the fork to your local computer and checkout the ``master``
   branch with ``git checkout master``. Optionally, create a new feature
   branch if you plan on working on multiple independent features at the
   same time. The branch name format we use is ``issue/XXX-ABCD`` where
   ``XXX`` is the GitHub issue number and ``ABCD`` is a one-or-two-word
   name for the issue. The command to create the branch is
   ``git checkout -b issue/XXX-ABCD``.

3. Make your changes and commit them (possibly in multiple commits).

    - Each commit should make a logical change
    - The commit message should consist of a short (50-ish characters,
      definitely less than 80)
    summary message on one line, followed optionally by a longer
    paragraph-form description (separated from the summary by a blank
    line)
    - The commit message summary should be descriptive and usually should
    start with a verb. "Updates" and "Fixed bugs" are not good commit
    messages. Examples from our repository:
        - Add script to generate controller config files
        - Add TimestampPacket to handle global timestamp synchronization
        - Create an explicit specification for larpix.logger.Logger objects
        - Fix bug in TimestampPacket.export

4. Push to your fork with ``git push`` if you're on master or this is
   not your first time pushing this branch, or
   ``git push -u origin issue/issue#-feature-name`` if it's your first time
   pushing this feature branch.

5. To update your branch in response to new code in the central
   repository:
    1. ``git remote add upstream https://github.com/larpix/larpix-control.git``
    (do this once)
    2. ``git fetch upstream master``
    3. ``git rebase upstream/master`` (preferred) or
    ``git merge upstream/master`` (if you insist)
    4. You will have to force-push to your personal fork if you rebased
    in step 3. First do a dry run: ``git push --force --dry-run`` and
    verify that the branch and remote address are correct. Then delete
    ``--dry-run`` and run ``git push --force``.

6. When your new feature is complete, or to solicit feedback on
   in-progress work, [open a pull
   request](https://help.github.com/en/articles/creating-a-pull-request-from-a-fork).
   :bangbang: ***Be sure to select a base repository of ``larpix/larpix-control`` and
   a base of ``master``. The default will be ``release`` but you should
   change it to ``master``!*** Cite the issue number you're working on in
   the body of the pull request. Select as a "reviewer" whoever you were
   communicating with about the feature you developed. We might suggest or
   require changes to be made before we (or you) merge in your work.

7. We use the "Merge Pull Request" button on the pull request page.

8. To update your fork to reflect your new changes:
    1. ``git checkout master``
    2. ``git fetch upstream master``
    3. ``git merge upstream/master``
    4. Once you're satisfied, you can delete your feature branch with
    ``git branch -d issue/issue#-feature-name``. Delete the remote
    branch on GitHub by navigating to the "branches" page under the
    "Code" tab on your fork. Then remove your local reference to the
    branch with ``git remote prune origin``.
    5. Push your updated master to your fork with ``git push``.

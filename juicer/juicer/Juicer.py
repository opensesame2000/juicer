# -*- coding: utf-8 -*-
# Juicer - Administer Pulp and Release Carts
# Copyright © 2012,2013, Red Hat, Inc.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

from juicer.common import Constants
from juicer.common.Errors import *
import juicer.common.Cart
import juicer.juicer
import juicer.utils
import juicer.utils.Upload
import os
import re


class Juicer(object):
    def __init__(self, args):
        self.args = args

        (self.connectors, self._defaults) = juicer.utils.get_login_info()

        if 'environment' in self.args:
            for env in self.args.environment:
                if env not in self.connectors.keys():
                    raise JuicerKeyError("%s is not an environment defined in juicer.conf" % env)

    # this is used to upload carts to pulp
	# opensesame modified this file
    def upload(self, env, cart):
        """
        Nothing special happens here. This method recieves a
        destination repo, and a payload of `cart` which will be
        uploaded into the target repo.

        Preparation: To use this method you must pre-process your
        cart: Remotes must be fetched and saved locally. Directories
        must be recursed and replaced with their contents. Items
        should be signed if necessary.

        Warning: this method trusts you to Do The Right Thing (TM),
        ahead of time and check file types before feeding them to it.

        `env` - name of the environment with the cart destination
        `cart` - cart to upload
        """
        for repo in cart.repos():
            if not juicer.utils.repo_exists_p(repo, self.connectors[env], env):
                juicer.utils.Log.log_info("repo '%s' doesn't exist in %s environment... skipping!",
                                          (repo, env))
                continue

            repoid = "%s-%s" % (repo, env)
            juicer.utils.Log.log_debug("Beginning upload into %s repo" % repoid)

            for item in cart[repo]:
                juicer.utils.Log.log_info("Initiating upload of '%s' into '%s'" % (item.path, repoid))
                rpm_id = juicer.utils.upload_rpm(item.path, repoid, self.connectors[env])
                juicer.utils.Log.log_debug('%s uploaded with an id of %s' %
                                           (os.path.basename(item.path), rpm_id))

            self.connectors[env].post('/repositories/%s/actions/publish/' % repoid, {'id': 'yum_distributor'})

            # Upload carts aren't special, don't update their paths
            if cart.cart_name == 'upload-cart':
                continue

            # Set the path to items in this cart to their location on
            # the pulp server.
            for item in cart[repo]:
                path = juicer.utils.remote_url(self.connectors[env],
                                               env,
                                               repo,
                                               os.path.basename(item.path))
                item.update(path)

        # Upload carts don't persist
        if not cart.cart_name == 'upload-cart':
            cart.save()
            self.publish(cart)
        return True

    def push(self, cart, env=None):
        """
        `cart` - Release cart to push items from

        Pushes the items in a release cart to the pre-release environment.
        """
        juicer.utils.Log.log_debug("Initializing push of cart '%s'" % cart.cart_name)

        if not env:
            env = self._defaults['start_in']

        self.sign_cart_for_env_maybe(cart, env)
        self.upload(env, cart)
        return True

    def publish(self, cart, env=None):
        """
        `cart` - Release cart to publish in json format

        Publish a release cart in JSON format to the pre-release environment.
        """
        juicer.utils.Log.log_debug("Initializing publish of cart '%s'" % cart.cart_name)

        if not env:
            env = self._defaults['start_in']

        cart_id = juicer.utils.upload_cart(cart, env)
        juicer.utils.Log.log_debug('%s uploaded with an id of %s' %
                                   (cart.cart_name, cart_id))
        return True

    def create(self, cart_name, cart_description):
        """
        `cart_name` - Name of this release cart
        `cart_description` - list of ['reponame', item1, ..., itemN] lists
        """
        cart = juicer.common.Cart.Cart(cart_name)

        # repo_items is a list that starts with the REPO name,
        # followed by the ITEMS going into the repo.
        for repo_items in cart_description:
            (repo, items) = (repo_items[0], repo_items[1:])
            juicer.utils.Log.log_debug("Processing %s input items for repo '%s'." % (len(items), repo))
            cart[repo] = items

        cart.save()
        return cart

    def update(self, cart_name, cart_description, manifests):
        """
        `cart_name` - Name of this release cart
        `cart_description` - list of ['reponame', item1, ..., itemN] lists
        `manifests` - a list of manifest files
        """
        if cart_description is None:
            juicer.utils.Log.log_debug("No cart_description provided.")
            cart_description = []

        if manifests is None:
            juicer.utils.Log.log_debug("No manifests provided.")
            manifests = []

        juicer.utils.Log.log_debug("Loading cart '%s'." % cart_name)
        cart = juicer.common.Cart.Cart(cart_name, autoload=True)

        for repo_items in cart_description:
            (repo, items) = (repo_items[0], repo_items[1:])
            juicer.utils.Log.log_debug("Processing %s input items for repo '%s'." % (len(items), repo))

            for item in items:
                cart[repo].append(juicer.common.CartItem.CartItem(os.path.expanduser(item)))

        for manifest in manifests:
            cart.add_from_manifest(manifest, self.connectors)

        cart.save()
        return cart

    def create_manifest(self, cart_name, manifests):
        """
        `cart_name` - Name of this release cart
        `manifests` - a list of manifest files
        """
        cart = juicer.common.Cart.Cart(cart_name)

        for manifest in manifests:
            cart.add_from_manifest(manifest, self.connectors)

        cart.save()
        return cart

    def show(self, cart_name):
        cart = juicer.common.Cart.Cart(cart_name)
        cart.load(cart_name)
        return str(cart)

    def search(self, pkg_name=None, search_carts=False, query='/content/units/rpm/search/'):
        """
        search for a package stored in a pulp repo

        `pkg_name` - substring in the name of the package
        `search_carts` - whether or not to return carts that include
            the listed package
        """
        # this data block is... yeah. searching in pulp v2 is painful
        #
        # https://pulp-dev-guide.readthedocs.org/en/latest/rest-api/content/retrieval.html#search-for-units
        # https://pulp-dev-guide.readthedocs.org/en/latest/rest-api/conventions/criteria.html#search-criteria
        #
        # those are the API docs for searching
        data = {
                    'criteria': {
                        'filters': {'name': {'$regex': ".*%s.*" % pkg_name}},
                        'sort': [['name', 'ascending']],
                        'fields': ['name', 'description', 'version', 'release', 'arch', 'filename']
                    },
                    'include_repos': 'true'
                }
        repos = []

        juicer.utils.Log.log_info('Packages:')

        for env in self.args.environment:
            juicer.utils.Log.log_debug("Querying %s server" % env)
            _r = self.connectors[env].post(query, data)

            if not _r.status_code == Constants.PULP_POST_OK:
                juicer.utils.Log.log_debug("Expected PULP_POST_OK, got %s", _r.status_code)
                _r.raise_for_status()

            juicer.utils.Log.log_info('%s:' % str.upper(env))

            pkg_list = juicer.utils.load_json_str(_r.content)

            for package in pkg_list:
                # if the package is in a repo, show a link to the package in said repo
                # otherwise, show nothing
                if len(package['repository_memberships']) > 0:
                    target = package['repository_memberships'][0]

                    _r = self.connectors[env].get('/repositories/%s/' % target)
                    if not _r.status_code == Constants.PULP_GET_OK:
                        raise JuicerPulpError("%s was not found as a repoid. A %s status code was returned" %
                                (target, _r.status_code))
                    repo = juicer.utils.load_json_str(_r.content)['display_name']
                    repos.append(repo)

                    link = juicer.utils.remote_url(self.connectors[env], env, repo, package['filename'])
                else:
                    link = ''

                juicer.utils.Log.log_info('%s\t%s\t%s\t%s' % (package['name'], package['version'], package['release'], link))

        if search_carts:
            # if the package is in a cart, show the cart name
            juicer.utils.Log.log_info('\nCarts:')

            for env in self.args.environment:
                carts = juicer.utils.search_carts(env, pkg_name, repos)
                for cart in carts:
                    juicer.utils.Log.log_info(cart['_id'])

    def hello(self):
        """
        Test pulp server connections defined in ~/.juicer.conf.
        """
        for env in self.args.environment:
            juicer.utils.Log.log_info("Trying to open a connection to %s, %s ...",
                                      env, self.connectors[env].base_url)
            try:
                _r = self.connectors[env].get()
                juicer.utils.Log.log_info("OK")
            except JuicerError:
                juicer.utils.Log.log_info("FAILED")
                continue

            juicer.utils.Log.log_info("Attempting to authenticate as %s",
                                      self.connectors[env].auth[0])

            _r = self.connectors[env].get('/repositories/')

            if _r.status_code == Constants.PULP_GET_OK:
                juicer.utils.Log.log_info("OK")
            else:
                juicer.utils.Log.log_info("FAILED")
                juicer.utils.Log.log_info("Server said: %s", _r.content)
                continue
        return True

    def merge(self, carts=None, new_cart_name=None):
        """
        `carts` - A list of cart names
        `new_cart_name` - Resultant cart name

        Merge the contents of N carts into a new cart

        TODO: Sanity check that each cart in `carts` exists. Try
        'juicer pull'ing carts that can't be located locally. Then cry
        like a baby and error out.
        """
        if new_cart_name != None:
            cart_name = new_cart_name
        else:
            cart_name = carts[0]

        result_cart = juicer.common.Cart.Cart(cart_name)
        items_hash = {}
        for cart in carts:
            # 1. Grab items from each cart and shit them into result_cart
            tmpcart = juicer.common.Cart.Cart(cart, autoload=True)
            for repo, items in tmpcart.iterrepos():
                if str(repo) in [str(key) for key in items_hash.keys()]:
                    items_hash[str(repo)] += [str(item) for item in items]
                else:
                    items_hash[str(repo)] = [str(item) for item in items]
        # 2. Remove duplicates
        for key in items_hash.keys():
            items_hash[key] = list(set(items_hash[key]))
            # 3. Wrap it up
            result_cart[key] = items_hash[key]
        result_cart.save()
        # You can not fail at merging carts?
        return True

    def pull(self, cartname=None, env=None):
        """
        `cartname` - Name of cart

        Pull remote cart from the pre release (base) environment
        """
        if not env:
            env = self._defaults['start_in']
        juicer.utils.Log.log_debug("Initializing pulling cart: %s ...", cartname)

        cart_file = os.path.join(juicer.common.Cart.CART_LOCATION, cartname)
        cart_file += '.json'

        juicer.utils.write_json_document(cart_file, juicer.utils.download_cart(cartname, env))

        return True

    def promote(self, cart_name):
        """
        `name` - name of cart

        Promote a cart from its current environment to the next in the chain.
        """
        cart = juicer.common.Cart.Cart(cart_name=cart_name, autoload=True, autosync=True)
        old_env = cart.current_env
        cart.current_env = juicer.utils.get_next_environment(cart.current_env)

        # figure out what needs to be done to promote packages. If
        # packages are going between environments that are on the same
        # host and we don't need to sign them just associate with both
        # repos.
        if juicer.utils.env_same_host(old_env, cart.current_env) and (self.connectors[old_env].requires_signature == self.connectors[cart.current_env].requires_signature):
            juicer.utils.Log.log_info("Envs %s and %s exist on the same host, calling remote associate action" % (old_env, cart.current_env))
            juicer.utils.Log.log_info("Promoting %s from %s to %s" %
                    (cart_name, old_env, cart.current_env))
            # iterate through packages and associate to new repo
            for repo, items in cart.iterrepos():
                query = '/repositories/%s-%s/actions/associate/' % (repo, cart.current_env)
                for item in items:
                    source_repo_id = '%s-%s' % (repo, old_env)
                    data = {
                        'source_repo_id': str(source_repo_id),
                        'criteria': {
                            'type_ids': ['rpm'],
                            'filters': {
                                'unit': {
                                    'filename': str(item.path.split('/')[-1])
                                    }
                                }
                            }
                        }
                    _r = self.connectors[cart.current_env].post(query, data)
                    if _r.status_code != Constants.PULP_POST_ACCEPTED:
                        raise JuicerPulpError("Package association call was not accepted. Terminating!")
                    else:
                        # association was accepted so publish destination repo
                        self.connectors[cart.current_env].post('/repositories/%s-%s/actions/publish/' % (repo, cart.current_env), {'id': 'yum_distributor'})
            # we didn't bomb out yet so let the user know what's up
            juicer.utils.Log.log_info("Package association calls were accepted. Trusting that your packages existed in %s" % old_env)
            # we can save and publish here because upload does this too...
            cart.save()
            self.publish(cart)
        else:
            juicer.utils.Log.log_debug("Syncing down rpms...")
            cart.sync_remotes()
            self.sign_cart_for_env_maybe(cart, cart.current_env)

            juicer.utils.Log.log_info("Promoting %s from %s to %s" %
                    (cart_name, old_env, cart.current_env))

            for repo in cart.repos():
                juicer.utils.Log.log_debug("Promoting %s to %s in %s" %
                                           (cart[repo], repo, cart.current_env))
            # reiterating that upload will save and publish the cart
            self.upload(cart.current_env, cart)

    def sign_cart_for_env_maybe(self, cart, env=None):
        """
        Sign the items to upload, if the env requires a signature.

        `cart` - Cart to sign
        `envs` - The cart is signed if env has the property:
        requires_signature = True

        Will attempt to load the rpm_sign_plugin defined in
        ~/.juicer.conf, which must be a plugin inheriting from
        juicer.common.RpmSignPlugin. If available, we'll call
        cart.sign_items() with a reference to the
        rpm_sign_plugin.sign_rpms method.
        """
        if self.connectors[env].requires_signature:
            juicer.utils.Log.log_notice("%s requires RPM signatures", env)
            juicer.utils.Log.log_notice("Checking for rpm_sign_plugin definition ...")
            module_name = self._defaults['rpm_sign_plugin']
            if self._defaults['rpm_sign_plugin']:
                juicer.utils.Log.log_notice("Found rpm_sign_plugin definition: %s",
                                            self._defaults['rpm_sign_plugin'])
                juicer.utils.Log.log_notice("Attempting to load ...")

                try:
                    rpm_sign_plugin = __import__(module_name, fromlist=[module_name])
                    juicer.utils.Log.log_notice("Successfully loaded %s ...", module_name)
                    plugin_object = getattr(rpm_sign_plugin, module_name.split('.')[-1])
                    signer = plugin_object()
                    cart.sign_items(signer.sign_rpms)
                except ImportError as e:
                    juicer.utils.Log.log_notice("there was a problem using %s ... error: %s",
                                                module_name, e)

                if not juicer.utils.rpms_signed_p([item.path for item in cart.items()]):
                    raise JuicerNotSignedError('RPMs have not been signed.')

            else:
                raise JuicerConfigError("Did not find an rpm_sign_plugin in config file.")
            return True
        else:
            return None
